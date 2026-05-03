"""Role-Based Access Control (RBAC) service — DB-backed with roles, permissions, user assignments."""
from enum import Enum
from datetime import datetime, UTC
from typing import Dict, List, Optional

from sqlalchemy import delete, func, select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import UserModel
from models.response import ApiResponse, PaginatedData


# Default system roles
DEFAULT_ROLES = [
    {
        "name": "admin",
        "display_name": "Administrator",
        "description": "Full system access with all permissions",
        "is_system": True,
        "priority": 100,
    },
    {
        "name": "manager",
        "display_name": "Manager",
        "description": "Manage team and view reports",
        "is_system": True,
        "priority": 80,
    },
    {
        "name": "sales",
        "display_name": "Sales Representative",
        "description": "Manage customers and opportunities",
        "is_system": True,
        "priority": 60,
    },
    {
        "name": "support",
        "display_name": "Support Agent",
        "description": "View customers and tickets, manage support tasks",
        "is_system": True,
        "priority": 50,
    },
    {
        "name": "viewer",
        "display_name": "Viewer",
        "description": "Read-only access to assigned resources",
        "is_system": True,
        "priority": 10,
    },
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

# Default role → permission mappings
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [p[0] for p in DEFAULT_PERMISSIONS],  # all
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


class Permission(Enum):
    """Permission enumeration — kept for backward compatibility."""
    CUSTOMER_CREATE = "customer:create"
    CUSTOMER_READ = "customer:read"
    CUSTOMER_UPDATE = "customer:update"
    CUSTOMER_DELETE = "customer:delete"
    OPPORTUNITY_CREATE = "opportunity:create"
    OPPORTUNITY_READ = "opportunity:read"
    OPPORTUNITY_UPDATE = "opportunity:update"
    OPPORTUNITY_DELETE = "opportunity:delete"
    TICKET_CREATE = "ticket:create"
    TICKET_READ = "ticket:read"
    TICKET_UPDATE = "ticket:update"
    TICKET_DELETE = "ticket:delete"
    USER_MANAGE = "user:manage"
    USER_READ = "user:read"
    ADMIN_ALL = "admin:all"


def _ensure_tables_exist(session: AsyncSession) -> bool:
    """Create RBAC tables if they don't exist. Returns True if created."""
    tables_exist = session.execute(
        text("SELECT to_regclass('public.roles')"), {}
    ).scalar()
    if tables_exist:
        return False

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL DEFAULT 0,
            name VARCHAR(50) NOT NULL,
            display_name VARCHAR(100) NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            is_system BOOLEAN NOT NULL DEFAULT FALSE,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(tenant_id, name)
        )
    """))
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            display_name VARCHAR(255) NOT NULL DEFAULT '',
            category VARCHAR(50) NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id SERIAL PRIMARY KEY,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            UNIQUE(role_id, permission_id)
        )
    """))
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS user_roles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            tenant_id INTEGER NOT NULL DEFAULT 0,
            granted_by INTEGER DEFAULT 0,
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, role_id)
        )
    """))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id)"))
    return True


def _init_defaults(session: AsyncSession) -> None:
    """Insert default roles and permissions if tables are empty."""
    roles_exist = session.execute(text("SELECT COUNT(*) FROM roles")).scalar()
    if roles_exist > 0:
        return

    for role in DEFAULT_ROLES:
        session.execute(
            text("""
                INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority, created_at)
                VALUES (0, :name, :display_name, :description, :is_system, :priority, :now)
                ON CONFLICT DO NOTHING
            """),
            {**role, "now": datetime.now(UTC)},
        )

    for perm_name, display_name, category in DEFAULT_PERMISSIONS:
        session.execute(
            text("""
                INSERT INTO permissions (name, display_name, category, created_at)
                VALUES (:name, :display_name, :category, :now)
                ON CONFLICT DO NOTHING
            """),
            {"name": perm_name, "display_name": display_name, "category": category, "now": datetime.now(UTC)},
        )

    session.flush()

    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role_row = session.execute(
            text("SELECT id FROM roles WHERE name = :name AND tenant_id = 0"),
            {"name": role_name},
        ).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        for perm_name in perm_names:
            perm_row = session.execute(
                text("SELECT id FROM permissions WHERE name = :name"),
                {"name": perm_name},
            ).fetchone()
            if not perm_row:
                continue
            session.execute(
                text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:role_id, :perm_id)
                    ON CONFLICT DO NOTHING
                """),
                {"role_id": role_id, "perm_id": perm_row[0]},
            )


class RBACService:
    """DB-backed RBAC service — roles, permissions, user assignments, permission checks."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        if session is not None:
            _ensure_tables_exist(session)
            _init_defaults(session)

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
        """Create a custom role."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            text("""
                INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority, created_at)
                VALUES (:tenant_id, :name, :display_name, :description, :is_system, :priority, :now)
                RETURNING id, tenant_id, name, display_name, description, is_system, priority, created_at
            """),
            {
                "tenant_id": tenant_id, "name": name, "display_name": display_name or name,
                "description": description, "is_system": is_system, "priority": priority, "now": now,
            },
        )
        row = result.fetchone()
        if row is None:
            return ApiResponse.error(message="角色创建失败", code=400)
        role = {
            "id": row[0], "tenant_id": row[1], "name": row[2], "display_name": row[3],
            "description": row[4], "is_system": row[5], "priority": row[6], "created_at": row[7].isoformat(),
        }
        return ApiResponse.success(data=role, message="角色创建成功")

    async def list_roles(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 50,
        include_system: bool = True,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """List roles (system roles + custom tenant roles)."""
        conditions = "tenant_id = :tenant_id OR tenant_id = 0"
        params: Dict = {"tenant_id": tenant_id}
        if not include_system:
            conditions = "tenant_id = :tenant_id"
        count = await self.session.execute(
            text(f"SELECT COUNT(*) FROM roles WHERE {conditions}"),
            params,
        )
        total = count.scalar_one()
        offset = (page - 1) * page_size
        rows = await self.session.execute(
            text(f"""
                SELECT id, tenant_id, name, display_name, description, is_system, priority, created_at
                FROM roles WHERE {conditions}
                ORDER BY priority DESC, id ASC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": page_size, "offset": offset},
        )
        items = [
            {
                "id": r[0], "tenant_id": r[1], "name": r[2], "display_name": r[3],
                "description": r[4], "is_system": r[5], "priority": r[6], "created_at": r[7].isoformat(),
            }
            for r in rows.fetchall()
        ]
        return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)

    async def get_role(self, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Get a role by ID."""
        row = await self.session.execute(
            text("SELECT id, tenant_id, name, display_name, description, is_system, priority, created_at FROM roles WHERE id = :id AND (tenant_id = :tenant_id OR tenant_id = 0)"),
            {"id": role_id, "tenant_id": tenant_id},
        )
        r = row.fetchone()
        if r is None:
            return ApiResponse.error(message="角色不存在", code=404)
        return ApiResponse.success(data={
            "id": r[0], "tenant_id": r[1], "name": r[2], "display_name": r[3],
            "description": r[4], "is_system": r[5], "priority": r[6], "created_at": r[7].isoformat(),
        })

    async def delete_role(self, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Delete a custom role (system roles cannot be deleted)."""
        row = await self.session.execute(
            text("SELECT is_system FROM roles WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": role_id, "tenant_id": tenant_id},
        )
        r = row.fetchone()
        if r is None:
            return ApiResponse.error(message="角色不存在", code=404)
        if r[0]:
            return ApiResponse.error(message="系统角色不可删除", code=403)
        await self.session.execute(
            text("DELETE FROM roles WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": role_id, "tenant_id": tenant_id},
        )
        return ApiResponse.success(data={"id": role_id}, message="角色删除成功")

    async def update_role(self, role_id: int, tenant_id: int, **kwargs) -> ApiResponse[Dict]:
        """Update a role's display_name, description, priority."""
        allowed = {"display_name", "description", "priority"}
        values = {k: v for k, v in kwargs.items() if k in allowed}
        if not values:
            return ApiResponse.error(message="没有需要更新的字段", code=400)
        set_clause = ", ".join(f"{k} = :{k}" for k in values)
        values["id"] = role_id
        values["tenant_id"] = tenant_id
        result = await self.session.execute(
            text(f"UPDATE roles SET {set_clause} WHERE id = :id AND tenant_id = :tenant_id RETURNING id, tenant_id, name, display_name, description, is_system, priority, created_at"),
            values,
        )
        r = result.fetchone()
        if r is None:
            return ApiResponse.error(message="角色不存在", code=404)
        return ApiResponse.success(data={
            "id": r[0], "tenant_id": r[1], "name": r[2], "display_name": r[3],
            "description": r[4], "is_system": r[5], "priority": r[6], "created_at": r[7].isoformat(),
        }, message="角色更新成功")

    # -------------------------------------------------------------------------
    # Permission CRUD
    # -------------------------------------------------------------------------

    async def list_permissions(
        self,
        category: Optional[str] = None,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """List all permissions, optionally filtered by category."""
        params: Dict = {}
        where = ""
        if category:
            where = "WHERE category = :category"
            params["category"] = category
        rows = await self.session.execute(
            text(f"SELECT id, name, display_name, category, description, created_at FROM permissions {where} ORDER BY category, id"),
            params,
        )
        items = [
            {"id": r[0], "name": r[1], "display_name": r[2], "category": r[3], "description": r[4], "created_at": r[5].isoformat()}
            for r in rows.fetchall()
        ]
        return ApiResponse.paginated(items=items, total=len(items), page=1, page_size=len(items))

    async def list_role_permissions(self, role_id: int) -> ApiResponse[List[Dict]]:
        """List all permissions assigned to a role."""
        rows = await self.session.execute(
            text("""
                SELECT p.id, p.name, p.display_name, p.category, p.description
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = :role_id
                ORDER BY p.category, p.id
            """),
            {"role_id": role_id},
        )
        items = [{"id": r[0], "name": r[1], "display_name": r[2], "category": r[3], "description": r[4]} for r in rows.fetchall()]
        return ApiResponse.success(data=items)

    async def set_role_permissions(self, role_id: int, permission_names: List[str], tenant_id: int) -> ApiResponse[Dict]:
        """Replace all permissions for a role with the given list."""
        row = await self.session.execute(
            text("SELECT is_system FROM roles WHERE id = :id AND (tenant_id = :tenant_id OR tenant_id = 0)"),
            {"id": role_id, "tenant_id": tenant_id},
        )
        r = row.fetchone()
        if r is None:
            return ApiResponse.error(message="角色不存在", code=404)

        # Delete existing
        await self.session.execute(text("DELETE FROM role_permissions WHERE role_id = :role_id"), {"role_id": role_id})

        # Insert new
        for perm_name in permission_names:
            perm_row = await self.session.execute(
                text("SELECT id FROM permissions WHERE name = :name"),
                {"name": perm_name},
            )
            p = perm_row.fetchone()
            if p is None:
                continue
            await self.session.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"),
                {"role_id": role_id, "perm_id": p[0]},
            )
        return ApiResponse.success(data={"role_id": role_id, "permissions": permission_names}, message="权限分配成功")

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
        # Verify role is accessible
        role_row = await self.session.execute(
            text("SELECT id FROM roles WHERE id = :id AND (tenant_id = :tenant_id OR tenant_id = 0)"),
            {"id": role_id, "tenant_id": tenant_id},
        )
        if role_row.fetchone() is None:
            return ApiResponse.error(message="角色不存在", code=404)

        # Verify user exists in tenant
        user_row = await self.session.execute(
            text("SELECT id FROM users WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": user_id, "tenant_id": tenant_id},
        )
        if user_row.fetchone() is None:
            return ApiResponse.error(message="用户不存在", code=404)

        await self.session.execute(
            text("""
                INSERT INTO user_roles (user_id, role_id, tenant_id, granted_by, granted_at)
                VALUES (:user_id, :role_id, :tenant_id, :granted_by, :now)
                ON CONFLICT (user_id, role_id) DO UPDATE
                    SET granted_by = EXCLUDED.granted_by, granted_at = EXCLUDED.granted_at
                RETURNING id, user_id, role_id, tenant_id, granted_by, granted_at
            """),
            {"user_id": user_id, "role_id": role_id, "tenant_id": tenant_id, "granted_by": granted_by, "now": datetime.now(UTC)},
        )
        return ApiResponse.success(data={"user_id": user_id, "role_id": role_id}, message="角色分配成功")

    async def revoke_role_from_user(self, user_id: int, role_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Revoke a role from a user."""
        result = await self.session.execute(
            text("DELETE FROM user_roles WHERE user_id = :user_id AND role_id = :role_id AND tenant_id = :tenant_id RETURNING id"),
            {"user_id": user_id, "role_id": role_id, "tenant_id": tenant_id},
        )
        if result.fetchone() is None:
            return ApiResponse.error(message="该用户没有此角色", code=404)
        return ApiResponse.success(data={"user_id": user_id, "role_id": role_id}, message="角色撤销成功")

    async def get_user_roles(self, user_id: int) -> ApiResponse[List[Dict]]:
        """Get all roles assigned to a user."""
        rows = await self.session.execute(
            text("""
                SELECT r.id, r.name, r.display_name, r.description, r.is_system, r.priority
                FROM roles r
                JOIN user_roles ur ON ur.role_id = r.id
                WHERE ur.user_id = :user_id
                ORDER BY r.priority DESC
            """),
            {"user_id": user_id},
        )
        items = [
            {"id": r[0], "name": r[1], "display_name": r[2], "description": r[3], "is_system": r[4], "priority": r[5]}
            for r in rows.fetchall()
        ]
        return ApiResponse.success(data=items)

    async def get_user_permissions(self, user_id: int) -> ApiResponse[List[str]]:
        """Get all permission strings for a user (union of all assigned roles)."""
        rows = await self.session.execute(
            text("""
                SELECT DISTINCT p.name
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                JOIN user_roles ur ON ur.role_id = rp.role_id
                WHERE ur.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        return ApiResponse.success(data=[r[0] for r in rows.fetchall()])

    def has_permission(self, role: str, permission: Permission) -> bool:
        """Check if a role has a specific permission (legacy enum-based, no DB needed)."""
        if role not in DEFAULT_ROLE_PERMISSIONS:
            return False
        return permission.value in DEFAULT_ROLE_PERMISSIONS[role]

    def get_role_permissions(self, role: str) -> list[Permission]:
        """Get all permissions for a given role (legacy, from static map)."""
        perm_names = DEFAULT_ROLE_PERMISSIONS.get(role, [])
        return [p for p in Permission if p.value in perm_names]


    def check_permission_by_value(self, role: str, permission_value: str) -> bool:
        """Check permission by string value (legacy helper)."""
        try:
            permission = Permission(permission_value)
            return self.has_permission(role, permission)
        except ValueError:
            return False

    # -------------------------------------------------------------------------
    # Permission checking
    # -------------------------------------------------------------------------

    async def _has_permission_db(self, user_id: int, permission: str) -> bool:
        """Check if a user has a specific permission (DB-backed)."""
        row = await self.session.execute(
            text("""
                SELECT 1 FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                JOIN user_roles ur ON ur.role_id = rp.role_id
                WHERE ur.user_id = :user_id AND p.name = :perm
                LIMIT 1
            """),
            {"user_id": user_id, "perm": permission},
        )
        return row.fetchone() is not None

    async def require_permission(self, user_id: int, permission: str) -> ApiResponse[Dict]:
        """Check permission and return error if denied."""
        if not await self._has_permission_db(user_id, permission):
            return ApiResponse.error(message=f"权限不足: {permission}", code=403)
        return ApiResponse.success(data={"user_id": user_id, "permission": permission})

    # -------------------------------------------------------------------------
    # Bulk user role management
    # -------------------------------------------------------------------------

    async def set_user_roles(self, user_id: int, role_ids: List[int], tenant_id: int, granted_by: int = 0) -> ApiResponse[Dict]:
        """Replace all roles for a user with the given list."""
        user_row = await self.session.execute(
            text("SELECT id FROM users WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": user_id, "tenant_id": tenant_id},
        )
        if user_row.fetchone() is None:
            return ApiResponse.error(message="用户不存在", code=404)

        await self.session.execute(
            text("DELETE FROM user_roles WHERE user_id = :user_id AND tenant_id = :tenant_id"),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        for role_id in role_ids:
            await self.session.execute(
                text("""
                    INSERT INTO user_roles (user_id, role_id, tenant_id, granted_by, granted_at)
                    VALUES (:user_id, :role_id, :tenant_id, :granted_by, :now)
                    ON CONFLICT DO NOTHING
                """),
                {"user_id": user_id, "role_id": role_id, "tenant_id": tenant_id, "granted_by": granted_by, "now": datetime.now(UTC)},
            )
        return ApiResponse.success(data={"user_id": user_id, "role_ids": role_ids}, message="用户角色更新成功")

    async def list_users_with_role(self, role_id: int, tenant_id: int) -> ApiResponse[List[Dict]]:
        """List all users who have a specific role."""
        rows = await self.session.execute(
            text("""
                SELECT u.id, u.username, u.email, u.full_name, u.status, ur.granted_at
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                WHERE ur.role_id = :role_id AND ur.tenant_id = :tenant_id
                ORDER BY u.id
            """),
            {"role_id": role_id, "tenant_id": tenant_id},
        )
        items = [
            {"id": r[0], "username": r[1], "email": r[2], "full_name": r[3], "status": r[4], "granted_at": r[5].isoformat()}
            for r in rows.fetchall()
        ]
        return ApiResponse.success(data=items)