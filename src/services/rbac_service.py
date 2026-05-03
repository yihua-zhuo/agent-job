"""Role-Based Access Control (RBAC) service — DB-backed with SQLAlchemy ORM."""
from datetime import datetime, UTC
from typing import Dict, List, Optional

from sqlalchemy import delete, select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.rbac import RoleModel, PermissionModel, RolePermissionModel, UserRoleModel
from db.models.user import UserModel
from models.response import ApiResponse, PaginatedData


# Default system roles
DEFAULT_ROLES = [
    {"name": "admin", "display_name": "Administrator", "description": "Full system access with all permissions", "is_system": True, "priority": 100},
    {"name": "manager", "display_name": "Manager", "description": "Manage team and view reports", "is_system": True, "priority": 80},
    {"name": "sales", "display_name": "Sales Representative", "description": "Manage customers and opportunities", "is_system": True, "priority": 60},
    {"name": "support", "display_name": "Support Agent", "description": "View customers and tickets, manage support tasks", "is_system": True, "priority": 50},
    {"name": "viewer", "display_name": "Viewer", "description": "Read-only access to assigned resources", "is_system": True, "priority": 10},
]

# Default permissions
DEFAULT_PERMISSIONS = [
    # Customer
    ("customer:create", "Create Customer", "customer"),
    ("customer:read", "Read Customer", "customer"),
    ("customer:update", "Update Customer", "customer"),
    ("customer:delete", "Delete Customer", "customer"),
    # Opportunity
    ("opportunity:create", "Create Opportunity", "opportunity"),
    ("opportunity:read", "Read Opportunity", "opportunity"),
    ("opportunity:update", "Update Opportunity", "opportunity"),
    ("opportunity:delete", "Delete Opportunity", "opportunity"),
    # Ticket
    ("ticket:create", "Create Ticket", "ticket"),
    ("ticket:read", "Read Ticket", "ticket"),
    ("ticket:update", "Update Ticket", "ticket"),
    ("ticket:delete", "Delete Ticket", "ticket"),
    # User management
    ("user:manage", "Manage Users", "user"),
    ("user:read", "Read User", "user"),
    # Admin
    ("admin:all", "Full Admin Access", "admin"),
]

# Default role → permission name mappings
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [p[0] for p in DEFAULT_PERMISSIONS],
    "manager": [
        "customer:read", "customer:update",
        "opportunity:read", "opportunity:create", "opportunity:update",
        "ticket:read", "ticket:create", "ticket:update",
        "user:read",
    ],
    "sales": [
        "customer:read", "customer:create", "customer:update",
        "opportunity:read", "opportunity:create", "opportunity:update",
    ],
    "support": [
        "customer:read", "opportunity:read",
        "ticket:read", "ticket:create", "ticket:update",
    ],
    "viewer": [
        "customer:read",
        "opportunity:read",
        "ticket:read",
    ],
}


class Permission:
    """Permission value object — comparable by value for test compatibility."""
    __slots__ = ("value",)
    _registry_: Dict[str, "Permission"] = {}

    def __init__(self, value: str):
        self.value = value
        self._registry_[value] = self

    def __repr__(self) -> str:
        return f"Permission({self.value!r})"
    def __eq__(self, other) -> bool:
        if isinstance(other, Permission):
            return self.value == other.value
        return self.value == other
    def __hash__(self) -> int:
        return hash(self.value)
    def __rmul__(self, other) -> str:
        return self.value  # enables str * Permission


# Singleton instances for test compatibility
def _mk(value: str) -> Permission:
    return Permission(value)


CUSTOMER_CREATE = _mk("customer:create")
CUSTOMER_READ = _mk("customer:read")
CUSTOMER_UPDATE = _mk("customer:update")
CUSTOMER_DELETE = _mk("customer:delete")
OPPORTUNITY_CREATE = _mk("opportunity:create")
OPPORTUNITY_READ = _mk("opportunity:read")
OPPORTUNITY_UPDATE = _mk("opportunity:update")
OPPORTUNITY_DELETE = _mk("opportunity:delete")
TICKET_CREATE = _mk("ticket:create")
TICKET_READ = _mk("ticket:read")
TICKET_UPDATE = _mk("ticket:update")
TICKET_DELETE = _mk("ticket:delete")
USER_MANAGE = _mk("user:manage")
USER_READ = _mk("user:read")
ADMIN_ALL = _mk("admin:all")

# Namespace for test: Permission.CUSTOMER_READ style access
Permission.CUSTOMER_CREATE = CUSTOMER_CREATE
Permission.CUSTOMER_READ = CUSTOMER_READ
Permission.CUSTOMER_UPDATE = CUSTOMER_UPDATE
Permission.CUSTOMER_DELETE = CUSTOMER_DELETE
Permission.OPPORTUNITY_CREATE = OPPORTUNITY_CREATE
Permission.OPPORTUNITY_READ = OPPORTUNITY_READ
Permission.OPPORTUNITY_UPDATE = OPPORTUNITY_UPDATE
Permission.OPPORTUNITY_DELETE = OPPORTUNITY_DELETE
Permission.TICKET_CREATE = TICKET_CREATE
Permission.TICKET_READ = TICKET_READ
Permission.TICKET_UPDATE = TICKET_UPDATE
Permission.TICKET_DELETE = TICKET_DELETE
Permission.USER_MANAGE = USER_MANAGE
Permission.USER_READ = USER_READ
Permission.ADMIN_ALL = ADMIN_ALL


async def init_defaults(session: AsyncSession) -> None:
    """Insert default roles and permissions if the permissions table is empty."""
    result = await session.execute(select(func.count()).select_from(PermissionModel))
    if result.scalar_one() > 0:
        return

    # Insert default permissions
    for name, display_name, category in DEFAULT_PERMISSIONS:
        session.add(PermissionModel(name=name, display_name=display_name, category=category, description=""))

    # Insert default roles and link to permissions
    for role_def in DEFAULT_ROLES:
        role = RoleModel(tenant_id=0, **role_def, created_at=datetime.now(UTC))
        session.add(role)
        await session.flush()

        perm_names = DEFAULT_ROLE_PERMISSIONS.get(role_def["name"], [])
        if not perm_names:
            continue
        result = await session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(perm_names))
        )
        perms = result.scalars().all()
        for perm in perms:
            session.add(RolePermissionModel(role_id=role.id, permission_id=perm.id))


class RBACService:
    """DB-backed RBAC service — roles, permissions, user assignments, permission checks."""

    def __init__(self, session: "AsyncSession"):
        self.session = session
        self._require_session()

    def _require_db(self):
        """Ensure a real session is available before DB operations."""
        if self.session is None:
            raise RuntimeError(
                "RBACService requires a session. "
                "Use RBACService(get_db_session()) or provide one explicitly."
            )

    def _require_session(self):
        """Alias for _require_db for backward compat."""
        self._require_db()

    # -------------------------------------------------------------------------
    # Role CRUD
    # -------------------------------------------------------------------------

    async def create_role(
        self,
        tenant_id: int,
        name: str,
        display_name: str = "",
        description: str = "",
        is_system: bool = False,
        priority: int = 0,
    ) -> ApiResponse[Dict]:
        """Create a new role."""
        role = RoleModel(
            tenant_id=tenant_id,
            name=name,
            display_name=display_name or name,
            description=description,
            is_system=is_system,
            priority=priority,
            created_at=datetime.now(UTC),
        )
        self.session.add(role)
        await self.session.flush()
        return ApiResponse.success(data=role.to_dict(), message="角色创建成功")

    async def list_roles(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 50,
        include_system: bool = True,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """List roles (system roles + custom tenant roles)."""
        conditions = [
            or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0) if include_system
            else RoleModel.tenant_id == tenant_id
        ]
        # count
        count_result = await self.session.execute(
            select(func.count()).select_from(RoleModel).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        # fetch page
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(RoleModel)
            .where(and_(*conditions))
            .order_by(RoleModel.priority.desc(), RoleModel.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        roles = result.scalars().all()
        items = [r.to_dict() for r in roles]
        return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)

    async def get_role(self, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Get a role by ID."""
        result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        role = result.scalar_one_or_none()
        if role is None:
            return ApiResponse.error(message="角色不存在", code=404)
        return ApiResponse.success(data=role.to_dict())

    async def update_role(self, role_id: int, tenant_id: int, **kwargs) -> ApiResponse[Dict]:
        """Update a role's display_name, description, priority."""
        allowed = {"display_name", "description", "priority"}
        values = {k: v for k, v in kwargs.items() if k in allowed}
        if not values:
            return ApiResponse.error(message="没有需要更新的字段", code=400)

        result = await self.session.execute(
            select(RoleModel).where(
                and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id)
            )
        )
        role = result.scalar_one_or_none()
        if role is None:
            return ApiResponse.error(message="角色不存在", code=404)

        for key, val in values.items():
            setattr(role, key, val)
        await self.session.flush()
        return ApiResponse.success(data=role.to_dict(), message="角色更新成功")

    async def delete_role(self, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Delete a custom role (system roles cannot be deleted)."""
        result = await self.session.execute(
            select(RoleModel).where(and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id))
        )
        role = result.scalar_one_or_none()
        if role is None:
            return ApiResponse.error(message="角色不存在", code=404)
        if role.is_system:
            return ApiResponse.error(message="系统角色不可删除", code=403)
        await self.session.delete(role)
        return ApiResponse.success(data={"id": role_id}, message="角色删除成功")

    # -------------------------------------------------------------------------
    # Permission CRUD
    # -------------------------------------------------------------------------

    async def list_permissions(self, category: Optional[str] = None) -> ApiResponse[PaginatedData[Dict]]:
        """List all permissions, optionally filtered by category."""
        query = select(PermissionModel)
        if category:
            query = query.where(PermissionModel.category == category)
        query = query.order_by(PermissionModel.category, PermissionModel.id)
        result = await self.session.execute(query)
        perms = result.scalars().all()
        items = [p.to_dict() for p in perms]
        return ApiResponse.paginated(items=items, total=len(items), page=1, page_size=len(items))

    async def list_role_permissions(self, role_id: int, tenant_id: int) -> ApiResponse[List[Dict]]:
        """List all permissions assigned to a role."""
        # Tenant-ownership check: role must belong to this tenant or be shared (tenant_id=0)
        role_check = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_check.scalar_one_or_none() is None:
            return ApiResponse.error(message="角色不存在", code=404)
        result = await self.session.execute(
            select(PermissionModel)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .where(RolePermissionModel.role_id == role_id)
            .order_by(PermissionModel.category, PermissionModel.id)
        )
        perms = result.scalars().all()
        return ApiResponse.success(data=[p.to_dict() for p in perms])

    async def set_role_permissions(self, role_id: int, permission_names: List[str], tenant_id: int) -> ApiResponse[Dict]:
        """Replace all permissions for a role with the given list."""
        # Only allow editing tenant-owned roles (strict: not system/shared roles from other tenants)
        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id)
            )
        )
        role = role_result.scalar_one_or_none()
        if role is None:
            return ApiResponse.error(message="角色不存在或不可修改", code=404)

        # Validate all permission names exist before touching any mappings
        perm_result = await self.session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(permission_names))
        )
        perms = perm_result.scalars().all()
        found_names = {p.name for p in perms}
        missing = set(permission_names) - found_names
        if missing:
            return ApiResponse.error(message=f"不存在的权限: {', '.join(sorted(missing))}", code=400)

        # Delete existing mappings only after all validation passes
        await self.session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        for perm in perms:
            self.session.add(RolePermissionModel(role_id=role_id, permission_id=perm.id))
        await self.session.flush()
        return ApiResponse.success(
            data={"role_id": role_id, "permissions": [p.name for p in perms]},
            message="权限分配成功",
        )

    # -------------------------------------------------------------------------
    # User role assignments
    # -------------------------------------------------------------------------

    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        tenant_id: int,
        granted_by: int = 0,
    ) -> ApiResponse[Dict]:
        """Assign a role to a user."""
        # Verify user exists in tenant
        user_result = await self.session.execute(
            select(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_result.scalar_one_or_none() is None:
            return ApiResponse.error(message="用户不存在", code=404)

        # Verify role is accessible
        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_result.scalar_one_or_none() is None:
            return ApiResponse.error(message="角色不存在", code=404)

        # Check for existing assignment — no-op if already present
        existing = await self.session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            return ApiResponse.success(data={"user_id": user_id, "role_id": role_id}, message="角色已分配")

        # Upsert assignment
        assignment = UserRoleModel(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
        )
        self.session.add(assignment)
        await self.session.flush()
        return ApiResponse.success(data={"user_id": user_id, "role_id": role_id}, message="角色分配成功")

    async def revoke_role_from_user(self, user_id: int, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Revoke a role from a user."""
        result = await self.session.execute(
            delete(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
        )
        if result.rowcount == 0:
            return ApiResponse.error(message="该用户没有此角色", code=404)
        return ApiResponse.success(data={"user_id": user_id, "role_id": role_id}, message="角色撤销成功")

    async def get_user_roles(self, user_id: int, tenant_id: int) -> ApiResponse[List[Dict]]:
        """Get all roles assigned to a user in a given tenant."""
        result = await self.session.execute(
            select(RoleModel)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
            .order_by(RoleModel.priority.desc())
        )
        roles = result.scalars().all()
        return ApiResponse.success(data=[r.to_dict() for r in roles])

    async def get_user_permissions(self, user_id: int, tenant_id: int) -> ApiResponse[List[str]]:
        """Get all permission strings for a user (union of all assigned roles in this tenant)."""
        result = await self.session.execute(
            select(PermissionModel.name)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .join(UserRoleModel, UserRoleModel.role_id == RolePermissionModel.role_id)
            .where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
            .distinct()
        )
        return ApiResponse.success(data=[r[0] for r in result.fetchall()])


    def has_permission(self, role: str, permission: Permission) -> bool:
        """Sync check if a role has a specific permission (uses static map, no DB needed)."""
        perm_value = permission.value if isinstance(permission, Permission) else permission
        return perm_value in DEFAULT_ROLE_PERMISSIONS.get(role, [])

    def get_role_permissions(self, role: str) -> List[str]:
        """Get all permission value strings for a given role (from static map)."""
        return list(DEFAULT_ROLE_PERMISSIONS.get(role, []))

    def check_permission_by_value(self, role: str, permission_value: str) -> bool:
        """Sync check by string value."""
        return permission_value in DEFAULT_ROLE_PERMISSIONS.get(role, [])

    async def _has_permission_db(self, user_id: int, permission: str, tenant_id: int) -> bool:
        """Check if a user has a specific permission in a given tenant."""
        result = await self.session.execute(
            select(PermissionModel.id)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .join(UserRoleModel, UserRoleModel.role_id == RolePermissionModel.role_id)
            .where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.tenant_id == tenant_id,
                    PermissionModel.name == permission,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def require_permission(self, user_id: int, permission: str, tenant_id: int) -> ApiResponse[Dict]:
        """Check permission and return error if denied."""
        if not await self._has_permission_db(user_id, permission, tenant_id):
            return ApiResponse.error(message=f"权限不足: {permission}", code=403)
        return ApiResponse.success(data={"user_id": user_id, "permission": permission})

    async def set_user_roles(
        self,
        user_id: int,
        role_ids: List[int],
        tenant_id: int,
        granted_by: int = 0,
    ) -> ApiResponse[Dict]:
        """Replace all roles for a user with the given list."""
        # Verify user exists
        user_result = await self.session.execute(
            select(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_result.scalar_one_or_none() is None:
            return ApiResponse.error(message="用户不存在", code=404)

        # Validate all role_ids exist and belong to this tenant (or are system roles)
        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id.in_(role_ids),
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        roles = role_result.scalars().all()
        if len(roles) != len(role_ids):
            found_ids = {r.id for r in roles}
            invalid = [rid for rid in role_ids if rid not in found_ids]
            return ApiResponse.error(message=f"不存在的角色ID: {invalid}", code=400)

        # Delete existing assignments
        await self.session.execute(
            delete(UserRoleModel).where(
                and_(UserRoleModel.user_id == user_id, UserRoleModel.tenant_id == tenant_id)
            )
        )

        # Insert new assignments
        for role_id in role_ids:
            self.session.add(UserRoleModel(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                granted_by=granted_by,
                granted_at=datetime.now(UTC),
            ))
        await self.session.flush()
        return ApiResponse.success(data={"user_id": user_id, "role_ids": role_ids}, message="用户角色更新成功")

    async def list_users_with_role(self, role_id: int, tenant_id: int) -> ApiResponse[List[Dict]]:
        """List all users who have a specific role."""
        result = await self.session.execute(
            select(UserModel)
            .join(UserRoleModel, UserRoleModel.user_id == UserModel.id)
            .where(
                and_(
                    UserRoleModel.role_id == role_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
            .order_by(UserModel.id)
        )
        users = result.scalars().all()
        return ApiResponse.success(data=[{"id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name, "status": u.status} for u in users])


# Helper needed by list_roles
from sqlalchemy import or_
