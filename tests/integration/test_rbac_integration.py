"""Integration tests for RBAC schema.

Requires a real PostgreSQL database — run with:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/ -m integration -v

The RBAC migration (195a79d95b41) is applied against the test DB at session start
to ensure the roles, permissions, user_roles, and role_permissions tables are
present before tests run.
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.rbac import RoleModel
from db.models.user import UserModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.rbac_service import DEFAULT_PERMISSIONS, RBACService


async def _seed_rbac_data():
    """Seed RBAC roles and permissions directly via raw SQL.

    The RBAC migration (195a79d95b41) creates and seeds the tables, but
    integration tests start from ORM create_all() which creates empty tables.
    This function inserts the seed data into already-existing tables.

    Uses asyncpg (async) so it is safe to call inside async test fixtures.

    asyncpg is imported lazily here (not at module top) so the rest of the
    file can be imported in environments where asyncpg is not installed
    (e.g. type-checker only runs).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL must be set to run integration tests. "
            "Example: DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/db' pytest tests/integration/ -m integration -v"
        )
    # Strip async driver prefix so asyncpg gets a valid postgresql:// DSN
    import asyncpg

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    sync_url = sync_url.replace("postgresql+psycopg2://", "postgresql://", 1)

    conn = await asyncpg.connect(sync_url)
    try:
        # Permissions
        await conn.execute("""
            INSERT INTO permissions (name, display_name, category, description)
            VALUES
                ('customer:create','Create Customer','customer',''),
                ('customer:read','Read Customer','customer',''),
                ('customer:update','Update Customer','customer',''),
                ('customer:delete','Delete Customer','customer',''),
                ('opportunity:create','Create Opportunity','opportunity',''),
                ('opportunity:read','Read Opportunity','opportunity',''),
                ('opportunity:update','Update Opportunity','opportunity',''),
                ('opportunity:delete','Delete Opportunity','opportunity',''),
                ('ticket:create','Create Ticket','ticket',''),
                ('ticket:read','Read Ticket','ticket',''),
                ('ticket:update','Update Ticket','ticket',''),
                ('ticket:delete','Delete Ticket','ticket',''),
                ('user:manage','Manage Users','user',''),
                ('user:read','Read User','user',''),
                ('admin:all','Full Admin Access','admin','')
            ON CONFLICT DO NOTHING
        """)
        # Roles — must match services/rbac_service.py DEFAULT_ROLES
        await conn.execute("""
            INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority)
            VALUES
                (0,'admin','Administrator','Full system access',true,100),
                (0,'manager','Manager','Manage team',true,80),
                (0,'sales','Sales Representative','Manage customers and opportunities',true,60),
                (0,'support','Support Agent','View customers and tickets, manage support',true,50),
                (0,'viewer','Viewer','Read-only access',true,10)
            ON CONFLICT DO NOTHING
        """)
        # Role permissions — admin: all 15
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='admin' AND p.name IN (
                'customer:create','customer:read','customer:update','customer:delete',
                'opportunity:create','opportunity:read','opportunity:update','opportunity:delete',
                'ticket:create','ticket:read','ticket:update','ticket:delete',
                'user:manage','user:read','admin:all'
            )
            ON CONFLICT DO NOTHING
        """)
        # manager: 9 perms + user:read
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='manager' AND p.name IN (
                'customer:read','customer:update',
                'opportunity:read','opportunity:create','opportunity:update',
                'ticket:read','ticket:create','ticket:update','user:read'
            )
            ON CONFLICT DO NOTHING
        """)
        # sales: 6 perms
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='sales' AND p.name IN (
                'customer:read','customer:create','customer:update',
                'opportunity:read','opportunity:create','opportunity:update'
            )
            ON CONFLICT DO NOTHING
        """)
        # support: 5 perms
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='support' AND p.name IN (
                'customer:read',
                'opportunity:read',
                'ticket:read','ticket:create','ticket:update'
            )
            ON CONFLICT DO NOTHING
        """)
        # viewer: 3 perms
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='viewer' AND p.name IN ('customer:read','opportunity:read','ticket:read')
            ON CONFLICT DO NOTHING
        """)
    finally:
        await conn.close()


@pytest.fixture(scope="function", autouse=True)
async def seed_rbac_data(db_schema):
    """Seed RBAC data after db_schema truncates, before each test.

    The db_schema fixture resets all tables between tests; this fixture
    re-populates the RBAC seed rows so every test starts with the same
    baseline state.
    """
    await _seed_rbac_data()


@pytest.mark.integration
class TestRBACIntegration:
    """Integration tests for RBACService against a real DB."""

    async def test_roles_table_has_5_system_roles(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        roles, total = await svc.list_roles(tenant_id=tenant_id)
        assert total >= 5
        names = {r.name for r in roles}
        assert "admin" in names
        assert "viewer" in names

    async def test_permissions_table_has_15_permissions(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        perms, total = await svc.list_permissions()
        assert total == 15
        names = {p.name for p in perms}
        assert "admin:all" in names
        assert "customer:create" in names

    async def test_admin_role_has_all_permissions(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        # Look up admin role dynamically — do not hardcode role_id
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        assert admin_role is not None, "admin role not found in seed data"
        perms = await svc.list_role_permissions(role_id=admin_role.id, tenant_id=0)
        assert len(perms) == 15

    async def test_viewer_role_has_read_only_permissions(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        # Look up viewer role dynamically — do not hardcode role_id
        roles, _ = await svc.list_roles(tenant_id=0)
        viewer_role = next((r for r in roles if r.name == "viewer"), None)
        assert viewer_role is not None, "viewer role not found in seed data"
        perms = await svc.list_role_permissions(role_id=viewer_role.id, tenant_id=0)
        assert len(perms) == 3
        names = {p.name for p in perms}
        assert "customer:read" in names
        assert "opportunity:read" in names
        assert "ticket:read" in names
        assert "customer:create" not in names

    async def test_create_tenant_role(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="test_role",
            display_name="Test Role",
            description="A custom test role",
            is_system=False,
            priority=40,
        )
        assert role.tenant_id == tenant_id
        assert role.name == "test_role"
        assert role.is_system is False

    async def test_get_role_not_found(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_role(role_id=99999, tenant_id=0)

    async def test_update_tenant_role(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="updatable_role",
            display_name="Updatable Role",
            is_system=False,
            priority=30,
        )
        updated = await svc.update_role(role_id=role.id, tenant_id=tenant_id, display_name="Updated Name")
        assert updated.display_name == "Updated Name"

    async def test_assign_role_to_user(self, db_schema, tenant_id, async_session):
        from services.user_service import UserService

        user_svc = UserService(async_session)
        user = await user_svc.create_user(
            username="rbac_test_user",
            email="rbac_test@example.com",
            password="TestPass123!",
            role="admin",
            tenant_id=tenant_id,
        )

        svc = RBACService(async_session)
        # Look up admin role dynamically
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        assert admin_role is not None
        result = await svc.assign_role_to_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        assert result["role_id"] == admin_role.id
        assert result.get("already_assigned") is not True

        # Verify tenant_id on the user_roles row (not just the role object)
        from sqlalchemy import and_, select

        from db.models.rbac import UserRoleModel
        result = await async_session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user.id,
                    UserRoleModel.role_id == admin_role.id,
                )
            )
        )
        ur_rows = result.scalars().all()
        assert len(ur_rows) == 1
        assert ur_rows[0].tenant_id == tenant_id

    async def test_assign_duplicate_role_returns_already_assigned(self, db_schema, tenant_id, async_session):
        from services.user_service import UserService

        user_svc = UserService(async_session)
        user = await user_svc.create_user(
            username="rbac_dup_user",
            email="rbac_dup@example.com",
            password="TestPass123!",
            role="admin",
            tenant_id=tenant_id,
        )

        svc = RBACService(async_session)
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        assert admin_role is not None
        await svc.assign_role_to_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        result = await svc.assign_role_to_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        assert result.get("already_assigned") is True
        # Verify tenant_id on the user_roles row
        from sqlalchemy import and_, select

        from db.models.rbac import UserRoleModel
        result = await async_session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user.id,
                    UserRoleModel.role_id == admin_role.id,
                )
            )
        )
        ur_rows = result.scalars().all()
        assert len(ur_rows) == 1
        assert ur_rows[0].tenant_id == tenant_id

    async def test_revoke_role_from_user(self, db_schema, tenant_id, async_session):
        from services.user_service import UserService

        user_svc = UserService(async_session)
        user = await user_svc.create_user(
            username="revoke_test_user",
            email="revoke_test@example.com",
            password="TestPass123!",
            role="admin",
            tenant_id=tenant_id,
        )

        svc = RBACService(async_session)
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        assert admin_role is not None
        await svc.assign_role_to_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        result = await svc.revoke_role_from_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        assert result["role_id"] == admin_role.id

    async def test_revoke_nonexistent_role_raises(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        assert admin_role is not None
        with pytest.raises(NotFoundException):
            await svc.revoke_role_from_user(user_id=99999, role_id=admin_role.id, tenant_id=tenant_id)

    async def test_get_user_roles(self, db_schema, tenant_id, async_session):
        from services.user_service import UserService

        user_svc = UserService(async_session)
        user = await user_svc.create_user(
            username="multi_role_user",
            email="multi_role@example.com",
            password="TestPass123!",
            role="admin",
            tenant_id=tenant_id,
        )

        svc = RBACService(async_session)
        roles, _ = await svc.list_roles(tenant_id=0)
        admin_role = next((r for r in roles if r.name == "admin"), None)
        viewer_role = next((r for r in roles if r.name == "viewer"), None)
        assert admin_role is not None and viewer_role is not None
        await svc.assign_role_to_user(user_id=user.id, role_id=admin_role.id, tenant_id=tenant_id)
        await svc.assign_role_to_user(user_id=user.id, role_id=viewer_role.id, tenant_id=tenant_id)
        user_roles = await svc.get_user_roles(user_id=user.id, tenant_id=tenant_id)
        assert len(user_roles) == 2

    async def test_set_role_permissions(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="custom_perm_role",
            display_name="Custom Perm Role",
            is_system=False,
            priority=20,
        )
        perms = await svc.set_role_permissions(
            role_id=role.id,
            permission_names=["customer:read", "customer:create"],
            tenant_id=tenant_id,
        )
        assert len(perms) == 2
        # Verify full replacement (not append) by checking that only these 2 exist
        perms_check = await svc.list_role_permissions(role_id=role.id, tenant_id=tenant_id)
        assert len(perms_check) == 2
        names = {p.name for p in perms_check}
        assert names == {"customer:read", "customer:create"}

    async def test_set_role_permissions_invalid_permission_raises(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="bad_perm_role",
            display_name="Bad Perm Role",
            is_system=False,
            priority=20,
        )
        with pytest.raises(ValidationException):
            await svc.set_role_permissions(
                role_id=role.id,
                permission_names=["customer:read", "nonexistent:permission"],
                tenant_id=tenant_id,
            )

    async def test_custom_role_invisible_to_other_tenant(self, db_schema, tenant_id, async_session):
        """Tenant 1's custom role must not be visible when querying from tenant 2."""
        svc = RBACService(async_session)

        # Create a custom role for tenant_id
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="tenant_specific_role",
            display_name="Tenant Specific Role",
            is_system=False,
            priority=30,
        )
        assert role.tenant_id == tenant_id

        # Create another tenant with a different ID — use a fixed large offset
        # to avoid collision with real seeded tenant IDs in parallel test runs.
        other_tenant = tenant_id + 99999

        # Query roles from the other tenant — system roles (tenant 0) are visible,
        # but tenant_specific_role must not appear.
        roles_same, total_same = await svc.list_roles(tenant_id=other_tenant)
        names = {r.name for r in roles_same}
        assert "tenant_specific_role" not in names
        assert total_same >= 5
        assert any(r.name == "admin" and r.tenant_id == 0 for r in roles_same), \
            "admin should be a system role with tenant_id=0"
        assert any(r.name == "viewer" and r.tenant_id == 0 for r in roles_same), \
            "viewer should be a system role with tenant_id=0"


# ---------------------------------------------------------------------------
# Tests for the new role_management_router endpoints at /api/v1/rbac/mgmt/
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRoleManagementAPI:
    """Integration tests for the new role_management_router (issue #642)."""

    async def test_list_roles_returns_system_roles_initially(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        resp = await api_client.get("/api/v1/rbac/mgmt/roles")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        names = {r["name"] for r in body["data"]["items"]}
        assert "admin" in names

    async def test_list_roles_pagination_envelope(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        """Pagination: page=1 page_size=2 returns at most 2 items with total fields populated."""
        resp = await api_client.get("/api/v1/rbac/mgmt/roles?page=1&page_size=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] >= 5
        assert data["total_pages"] >= 1
        assert len(data["items"]) <= 2

    async def test_create_role_then_list_includes_it(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "custom_support", "permissions": ["customer:read"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "custom_support"
        assert body["data"]["tenant_id"] is not None
        assert "admin" not in body["data"] or body["data"]["is_system"] is False

        list_resp = await api_client.get("/api/v1/rbac/mgmt/roles")
        names = {r["name"] for r in list_resp.json()["data"]["items"]}
        assert "custom_support" in names

    async def test_create_role_with_unknown_permission_returns_422(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "bad_perms", "permissions": ["fake:perm"]},
        )
        assert resp.status_code == 422

    async def test_update_role_permissions_replaces_existing(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        create_resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "upd_test", "permissions": ["customer:read"]},
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["data"]["id"]

        update_resp = await api_client.put(
            f"/api/v1/rbac/mgmt/roles/{role_id}/permissions",
            json={"permissions": ["opportunity:read", "ticket:read"]},
        )
        assert update_resp.status_code == 200, update_resp.text

        get_resp = await api_client.get(
            f"/api/v1/rbac/mgmt/roles/{role_id}/permissions"
        )
        perms = get_resp.json()["data"]["permissions"]
        assert "opportunity:read" in perms
        assert "ticket:read" in perms
        assert "customer:read" not in perms

    async def test_update_role_permissions_empty_list_returns_422(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        create_resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "upd_empty", "permissions": ["customer:read"]},
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["data"]["id"]
        resp = await api_client.put(
            f"/api/v1/rbac/mgmt/roles/{role_id}/permissions",
            json={"permissions": []},
        )
        assert resp.status_code == 422

    async def test_update_system_role_permissions_returns_403(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        result = await async_session.execute(
            select(RoleModel).where(RoleModel.name == "admin")
        )
        admin_role = result.scalar_one()
        resp = await api_client.put(
            f"/api/v1/rbac/mgmt/roles/{admin_role.id}/permissions",
            json={"permissions": ["customer:read"]},
        )
        assert resp.status_code == 403

    async def test_assign_role_to_user_persists_binding(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        result = await async_session.execute(
            select(RoleModel).where(RoleModel.name == "admin")
        )
        admin_role = result.scalar_one()

        result = await async_session.execute(
            select(UserModel).where(UserModel.username == "webtest")
        )
        user = result.scalar_one()

        resp = await api_client.post(
            f"/api/v1/rbac/mgmt/users/{user.id}/role",
            json={"role_id": admin_role.id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["role_id"] == admin_role.id
        assert body["data"]["user_id"] == user.id
        # First call is not idempotent, so already_assigned should be False / unset
        assert body["data"].get("already_assigned") is not True
        assert body["message"] == "角色分配成功"

        # Second call must return already_assigned=True and a different message
        resp2 = await api_client.post(
            f"/api/v1/rbac/mgmt/users/{user.id}/role",
            json={"role_id": admin_role.id},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["data"].get("already_assigned") is True
        assert body2["message"] == "角色已分配"

    async def test_list_permissions_returns_all_system_pairs(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        resp = await api_client.get("/api/v1/rbac/mgmt/permissions")
        assert resp.status_code == 200
        perms = resp.json()["data"]
        assert len(perms) == len(DEFAULT_PERMISSIONS)
        for entry in perms:
            assert set(entry.keys()) == {"resource", "action"}
            assert entry["resource"]
            assert entry["action"]

    async def test_tenant_isolation_roles(
        self,
        api_client: AsyncClient,
        api_client_tenant_2: AsyncClient,
        async_session: AsyncSession,
        db_schema,
    ):
        create_resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "tenant1_only_role", "permissions": ["customer:read"]},
        )
        assert create_resp.status_code == 201
        custom = create_resp.json()["data"]
        custom_name = custom["name"]
        # The response must carry the tenant_id so callers can confirm the
        # role belongs to tenant 1 (not just rely on absence in tenant 2).
        assert custom["tenant_id"] != 0
        assert custom["tenant_id"] is not None

        list1 = await api_client.get("/api/v1/rbac/mgmt/roles")
        items1 = list1.json()["data"]["items"]
        names1 = {r["name"] for r in items1}
        assert custom_name in names1
        # Verify tenant_id on the listed custom role entry
        role1 = next(r for r in items1 if r["name"] == custom_name)
        assert role1["tenant_id"] == custom["tenant_id"]
        assert role1["is_system"] is False

        list2 = await api_client_tenant_2.get("/api/v1/rbac/mgmt/roles")
        names2 = {r["name"] for r in list2.json()["data"]["items"]}
        assert custom_name not in names2
        # Tenant 2 should still see the 5 system roles
        assert "admin" in names2
        assert "viewer" in names2

    async def test_get_role_permissions_for_custom_role(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        create_resp = await api_client.post(
            "/api/v1/rbac/mgmt/roles",
            json={"name": "get_perms_test", "permissions": ["customer:read", "opportunity:read"]},
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["data"]["id"]

        get_resp = await api_client.get(
            f"/api/v1/rbac/mgmt/roles/{role_id}/permissions"
        )
        assert get_resp.status_code == 200
        data = get_resp.json()["data"]
        assert data["role_id"] == role_id
        assert set(data["permissions"]) == {"customer:read", "opportunity:read"}

    async def test_create_role_duplicate_name_returns_409(
        self, api_client: AsyncClient, async_session: AsyncSession, db_schema
    ):
        body = {"name": "dup_test", "permissions": ["customer:read"]}
        first = await api_client.post("/api/v1/rbac/mgmt/roles", json=body)
        assert first.status_code == 201

        second = await api_client.post("/api/v1/rbac/mgmt/roles", json=body)
        assert second.status_code == 409

    async def test_create_role_denies_non_admin(
        self, db_schema, async_session: AsyncSession
    ):
        """A JWT with no `admin` role must be denied (403) for write endpoints.

        Constructs a token without `roles: ["admin"]` to verify the gate.
        """
        from datetime import UTC, datetime, timedelta

        import jwt as _jwt
        from httpx import ASGITransport
        from httpx import AsyncClient as _AC

        from db.connection import get_db
        from db.models.tenant import TenantModel
        from main import app as _app
        from services.user_service import UserService

        tid = 42_000_001
        result = await async_session.execute(select(TenantModel).where(TenantModel.id == tid))
        if result.scalar_one_or_none() is None:
            async_session.add(TenantModel(id=tid, name="NoAdmin Tenant", plan="free", status="active"))
            await async_session.flush()

        user_svc = UserService(async_session)
        existing = await user_svc.get_user_by_username(tid, "nonadmin")
        if existing is None:
            await user_svc.create_user(
                username="nonadmin",
                email="nonadmin@example.com",
                password="TestPass123!",
                role="viewer",
                tenant_id=tid,
            )

        now = datetime.now(UTC)
        token = _jwt.encode(
            {
                "user_id": 1,
                "username": "nonadmin",
                "role": "viewer",
                "roles": ["viewer"],
                "iat": now,
                "exp": now + timedelta(hours=1),
                "tenant_id": tid,
            },
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

        async def _override_get_db():
            yield async_session

        _app.dependency_overrides[get_db] = _override_get_db
        try:
            transport = ASGITransport(app=_app)
            async with _AC(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as ac:
                resp = await ac.post(
                    "/api/v1/rbac/mgmt/roles",
                    json={"name": "viewer_attempt", "permissions": ["customer:read"]},
                )
                assert resp.status_code == 403, resp.text
        finally:
            _app.dependency_overrides.pop(get_db, None)
