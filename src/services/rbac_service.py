"""Role-Based Access Control (RBAC) service — DB-backed with SQLAlchemy ORM."""
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.rbac import PermissionModel, RoleModel, RolePermissionModel, UserRoleModel
from db.models.user import UserModel
from pkg.errors.app_exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)

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
    ("customer:create", "Create Customer", "customer"),
    ("customer:read", "Read Customer", "customer"),
    ("customer:update", "Update Customer", "customer"),
    ("customer:delete", "Delete Customer", "customer"),
    ("opportunity:create", "Create Opportunity", "opportunity"),
    ("opportunity:read", "Read Opportunity", "opportunity"),
    ("opportunity:update", "Update Opportunity", "opportunity"),
    ("opportunity:delete", "Delete Opportunity", "opportunity"),
    ("ticket:create", "Create Ticket", "ticket"),
    ("ticket:read", "Read Ticket", "ticket"),
    ("ticket:update", "Update Ticket", "ticket"),
    ("ticket:delete", "Delete Ticket", "ticket"),
    ("user:manage", "Manage Users", "user"),
    ("user:read", "Read User", "user"),
    ("admin:all", "Full Admin Access", "admin"),
]

# Default role → permission name mappings
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
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
    """Permission value object — comparable by value for test compatibility.

    Creating an instance auto-registers it as a class attribute::

        Permission("customer:create")  # → Permission.CUSTOMER_CREATE
    """
    __slots__ = ("value",)

    def __init__(self, value: str):
        self.value = value
        attr = value.replace(":", "_").upper()
        setattr(type(self), attr, self)

    def __repr__(self) -> str:
        return f"Permission({self.value!r})"

    def __eq__(self, other) -> bool:
        if isinstance(other, Permission):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return hash(self.value)


# Create all permission instances (auto-registered as Permission.CUSTOMER_CREATE, etc.)
for _name, _, _ in DEFAULT_PERMISSIONS:
    Permission(_name)


async def init_defaults(session: AsyncSession) -> None:
    """Insert default roles and permissions if they don't exist yet."""
    perm_count = await session.execute(select(func.count()).select_from(PermissionModel))
    if perm_count.scalar_one() == 0:
        for name, display_name, category in DEFAULT_PERMISSIONS:
            session.add(PermissionModel(name=name, display_name=display_name, category=category, description=""))
        await session.flush()

    role_count = await session.execute(select(func.count()).select_from(RoleModel))
    if role_count.scalar_one() == 0:
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
            for perm in result.scalars().all():
                session.add(RolePermissionModel(role_id=role.id, permission_id=perm.id))


class RBACService:
    """DB-backed RBAC service.

    - Returns ORM model objects on success.
    - Raises AppException subclasses on errors.
    - Router handles serialization (.to_dict()) and response envelope.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

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
    ) -> RoleModel:
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
        return role

    async def list_roles(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 50,
        include_system: bool = True,
    ) -> tuple[list[RoleModel], int]:
        conditions = [
            or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0) if include_system
            else RoleModel.tenant_id == tenant_id
        ]
        count_result = await self.session.execute(
            select(func.count()).select_from(RoleModel).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(RoleModel)
            .where(and_(*conditions))
            .order_by(RoleModel.priority.desc(), RoleModel.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def get_role(self, role_id: int, tenant_id: int) -> RoleModel:
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
            raise NotFoundException("角色")
        return role

    async def update_role(self, role_id: int, tenant_id: int, **kwargs) -> RoleModel:
        allowed = {"display_name", "description", "priority"}
        values = {k: v for k, v in kwargs.items() if k in allowed}
        if not values:
            raise ValidationException("没有需要更新的字段")

        result = await self.session.execute(
            select(RoleModel).where(
                and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id)
            )
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise NotFoundException("角色")

        for key, val in values.items():
            setattr(role, key, val)
        await self.session.flush()
        return role

    async def delete_role(self, role_id: int, tenant_id: int) -> int:
        result = await self.session.execute(
            select(RoleModel).where(and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id))
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise NotFoundException("角色")
        if role.is_system:
            raise ForbiddenException("系统角色不可删除")
        await self.session.delete(role)
        return role_id

    # -------------------------------------------------------------------------
    # Permission CRUD
    # -------------------------------------------------------------------------

    async def list_permissions(
        self,
        category: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PermissionModel], int]:
        base = select(PermissionModel)
        if category:
            base = base.where(PermissionModel.category == category)

        count_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            base.order_by(PermissionModel.category, PermissionModel.id)
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def list_role_permissions(self, role_id: int, tenant_id: int) -> list[PermissionModel]:
        role_check = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_check.scalar_one_or_none() is None:
            raise NotFoundException("角色")
        result = await self.session.execute(
            select(PermissionModel)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .where(RolePermissionModel.role_id == role_id)
            .order_by(PermissionModel.category, PermissionModel.id)
        )
        return result.scalars().all()

    async def set_role_permissions(
        self, role_id: int, permission_names: list[str], tenant_id: int,
    ) -> list[PermissionModel]:
        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(RoleModel.id == role_id, RoleModel.tenant_id == tenant_id)
            )
        )
        if role_result.scalar_one_or_none() is None:
            raise NotFoundException("角色")

        permission_names = list(dict.fromkeys(permission_names))

        perm_result = await self.session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(permission_names))
        )
        perms = perm_result.scalars().all()
        found_names = {p.name for p in perms}
        missing = set(permission_names) - found_names
        if missing:
            raise ValidationException(f"不存在的权限: {', '.join(sorted(missing))}")

        await self.session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        for perm in perms:
            self.session.add(RolePermissionModel(role_id=role_id, permission_id=perm.id))
        await self.session.flush()
        return perms

    # -------------------------------------------------------------------------
    # User role assignments
    # -------------------------------------------------------------------------

    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        tenant_id: int,
        granted_by: int = 0,
    ) -> dict:
        user_result = await self.session.execute(
            select(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_result.scalar_one_or_none() is None:
            raise NotFoundException("用户")

        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_result.scalar_one_or_none() is None:
            raise NotFoundException("角色")

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
            return {"user_id": user_id, "role_id": role_id, "already_assigned": True}

        self.session.add(UserRoleModel(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
        ))
        await self.session.flush()
        return {"user_id": user_id, "role_id": role_id}

    async def revoke_role_from_user(self, user_id: int, role_id: int, tenant_id: int) -> dict:
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
            raise NotFoundException("用户角色")
        return {"user_id": user_id, "role_id": role_id}

    async def get_user_roles(self, user_id: int, tenant_id: int) -> list[RoleModel]:
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
        return result.scalars().all()

    async def get_user_permissions(self, user_id: int, tenant_id: int) -> list[str]:
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
        return [r[0] for r in result.fetchall()]

    # -------------------------------------------------------------------------
    # Static permission checks (use DEFAULT_ROLE_PERMISSIONS, no DB)
    # -------------------------------------------------------------------------

    @staticmethod
    def has_permission(role: str, permission: Permission | str) -> bool:
        perm_value = permission.value if isinstance(permission, Permission) else permission
        return perm_value in DEFAULT_ROLE_PERMISSIONS.get(role, [])

    @staticmethod
    def get_role_permissions(role: str) -> list[str]:
        return list(DEFAULT_ROLE_PERMISSIONS.get(role, []))

    @staticmethod
    def check_permission_by_value(role: str, permission_value: str) -> bool:
        return permission_value in DEFAULT_ROLE_PERMISSIONS.get(role, [])

    # -------------------------------------------------------------------------
    # DB-backed permission checks
    # -------------------------------------------------------------------------

    async def has_permission_db(self, user_id: int, permission: str, tenant_id: int) -> bool:
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

    async def require_permission(self, user_id: int, permission: str, tenant_id: int) -> None:
        if not await self.has_permission_db(user_id, permission, tenant_id):
            raise ForbiddenException(f"权限不足: {permission}")

    async def set_user_roles(
        self,
        user_id: int,
        role_ids: list[int],
        tenant_id: int,
        granted_by: int = 0,
    ) -> list[int]:
        user_result = await self.session.execute(
            select(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_result.scalar_one_or_none() is None:
            raise NotFoundException("用户")

        role_ids = list(dict.fromkeys(role_ids))

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
            raise ValidationException(f"不存在的角色ID: {invalid}")

        await self.session.execute(
            delete(UserRoleModel).where(
                and_(UserRoleModel.user_id == user_id, UserRoleModel.tenant_id == tenant_id)
            )
        )
        for role_id in role_ids:
            self.session.add(UserRoleModel(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                granted_by=granted_by,
                granted_at=datetime.now(UTC),
            ))
        await self.session.flush()
        return role_ids

    async def list_users_with_role(self, role_id: int, tenant_id: int) -> list[UserModel]:
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
        return result.scalars().all()
