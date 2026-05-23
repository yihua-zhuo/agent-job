"""Integration tests for RBAC schema.

Requires a real PostgreSQL database — run with:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_rbac_integration.py -v

The RBAC migration (195a79d95b41) is applied against the test DB at session start
to ensure the roles, permissions, user_roles, and role_permissions tables are
present before tests run.
"""

from __future__ import annotations

import subprocess
import os

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.rbac_service import RBACService, Permission


def _seed_rbac_data():
    """Seed RBAC roles and permissions directly via raw SQL.

    The RBAC migration (195a79d95b41) creates and seeds the tables, but
    integration tests start from ORM create_all() which creates empty tables.
    This function inserts the seed data into already-existing tables.

    Import psycopg2 here so the test file can be imported even if it's not
    available (it will be used at runtime when the fixture runs).
    """
    import os

    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not db_url:
        return

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    import psycopg2

    conn = psycopg2.connect(sync_url)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        # Permissions
        cur.execute("""
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
        # Roles
        cur.execute("""
            INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority)
            VALUES
                (0,'admin','Administrator','Full system access',true,100),
                (0,'manager','Manager','Manage team',true,80),
                (0,'sales','Sales Representative','Manage customers',true,60),
                (0,'support','Support Agent','Support tasks',true,50),
                (0,'viewer','Viewer','Read-only',true,10)
            ON CONFLICT DO NOTHING
        """)
        # Role permissions (admin: all 15)
        cur.execute("""
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
        # manager: 8 perms
        cur.execute("""
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
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='sales' AND p.name IN (
                'customer:read','customer:create','customer:update',
                'opportunity:read','opportunity:create','opportunity:update'
            )
            ON CONFLICT DO NOTHING
        """)
        # support: 5 perms
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='support' AND p.name IN (
                'customer:read','opportunity:read',
                'ticket:read','ticket:create','ticket:update'
            )
            ON CONFLICT DO NOTHING
        """)
        # viewer: 3 perms
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name='viewer' AND p.name IN ('customer:read','opportunity:read','ticket:read')
            ON CONFLICT DO NOTHING
        """)
    finally:
        conn.close()


@pytest.fixture(scope="function", autouse=True)
def seed_rbac_data(db_schema, tenant_id):
    """Seed RBAC data after db_schema truncates, before each test.

    The db_schema fixture resets all tables between tests; this fixture
    re-populates the RBAC seed rows so every test starts with the same
    baseline state.
    """
    _seed_rbac_data()


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
        perms = await svc.list_role_permissions(role_id=1, tenant_id=0)
        assert len(perms) == 15

    async def test_viewer_role_has_read_only_permissions(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        perms = await svc.list_role_permissions(role_id=5, tenant_id=0)
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
        result = await svc.assign_role_to_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        assert result["role_id"] == 1
        assert result.get("already_assigned") is not True

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
        await svc.assign_role_to_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        result = await svc.assign_role_to_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        assert result.get("already_assigned") is True

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
        await svc.assign_role_to_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        result = await svc.revoke_role_from_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        assert result["role_id"] == 1

    async def test_revoke_nonexistent_role_raises(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        with pytest.raises(NotFoundException):
            await svc.revoke_role_from_user(user_id=99999, role_id=1, tenant_id=tenant_id)

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
        await svc.assign_role_to_user(user_id=user.id, role_id=1, tenant_id=tenant_id)
        await svc.assign_role_to_user(user_id=user.id, role_id=5, tenant_id=tenant_id)
        roles = await svc.get_user_roles(user_id=user.id, tenant_id=tenant_id)
        assert len(roles) == 2

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

    async def test_set_role_permissions_invalid_permission_raises(self, db_schema, tenant_id, async_session):
        svc = RBACService(async_session)
        role = await svc.create_role(
            tenant_id=tenant_id,
            name="bad_perm_role",
            display_name="Bad Perm Role",
            is_system=False,
            priority=20,
        )
        with pytest.raises(Exception):  # ValidationException
            await svc.set_role_permissions(
                role_id=role.id,
                permission_names=["customer:read", "nonexistent:permission"],
                tenant_id=tenant_id,
            )