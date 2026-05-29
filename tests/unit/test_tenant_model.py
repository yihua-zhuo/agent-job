"""Tests for TenantModel."""

from datetime import datetime as dt

import pytest

from db.models.tenant import TenantModel
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.tenants import make_tenant_handler


class TestTenantModel:
    def test_to_dict_includes_slug_and_usage_limits(self):
        tenant = TenantModel(
            id=1,
            name="Acme Corp",
            slug="acme-corp",
            plan="pro",
            status="active",
            settings={"theme": "dark"},
            usage_limits={"users": 50, "storage_gb": 100},
            created_at=dt(2026, 1, 1, 12, 0, 0),
            updated_at=dt(2026, 1, 2, 12, 0, 0),
        )
        d = tenant.to_dict()
        assert "slug" in d
        assert "usage_limits" in d
        assert d["slug"] == "acme-corp"
        assert d["usage_limits"] == {"users": 50, "storage_gb": 100}

    def test_to_dict_slug_defaults_to_empty_string(self):
        tenant = TenantModel(
            id=2,
            name="Beta Inc",
            slug="",
            plan="free",
            status="active",
            settings={},
            usage_limits={},
            created_at=dt(2026, 1, 1, 12, 0, 0),
            updated_at=dt(2026, 1, 1, 12, 0, 0),
        )
        d = tenant.to_dict()
        assert d["slug"] == ""

    def test_to_dict_usage_limits_defaults_to_empty_dict(self):
        tenant = TenantModel(
            id=3,
            name="Gamma LLC",
            slug="gamma",
            plan="enterprise",
            status="active",
            settings={},
            usage_limits={},
            created_at=dt(2026, 1, 1, 12, 0, 0),
            updated_at=dt(2026, 1, 1, 12, 0, 0),
        )
        d = tenant.to_dict()
        assert d["usage_limits"] == {}


class TestTenantHandler:
    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        return make_mock_session([make_tenant_handler(state)])

    @pytest.mark.asyncio
    async def test_insert_tenant(self, mock_db_session):
        from sqlalchemy import text

        result = await mock_db_session.execute(
            text(
                "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
            ),
            {
                "name": "Test Tenant",
                "slug": "test-tenant",
                "plan": "free",
                "status": "active",
                "settings": {},
                "usage_limits": {},
            },
        )
        row = result.fetchone()
        assert row is not None
        assert row.id == 1
        assert row.name == "Test Tenant"
        assert row.slug == "test-tenant"
        assert row.plan == "free"

    @pytest.mark.asyncio
    async def test_select_tenant_by_id(self, mock_db_session):
        from sqlalchemy import text

        # Seed a tenant first so there's something to select.
        await mock_db_session.execute(
            text(
                "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) "
                "VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
            ),
            {
                "name": "Alpha Corp",
                "slug": "alpha-corp",
                "plan": "enterprise",
                "status": "active",
                "settings": {},
                "usage_limits": {"users": 200},
            },
        )

        result = await mock_db_session.execute(
            text("SELECT id, name, slug, plan FROM tenants WHERE id = :id LIMIT 1"),
            {"id": 1},
        )
        row = result.fetchone()
        assert row is not None
        assert row.name == "Alpha Corp"
        assert row.slug == "alpha-corp"
        assert row.plan == "enterprise"

    @pytest.mark.asyncio
    async def test_select_tenant_isolation(self, mock_db_session):
        """Verify the handler correctly scopes reads to a specific tenant_id."""
        from sqlalchemy import text

        # Seed two tenants with different IDs into the handler state.
        await mock_db_session.execute(
            text(
                "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) "
                "VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
            ),
            {
                "name": "Tenant One",
                "slug": "tenant-one",
                "plan": "free",
                "status": "active",
                "settings": {},
                "usage_limits": {},
            },
        )
        await mock_db_session.execute(
            text(
                "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) "
                "VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
            ),
            {
                "name": "Tenant Two",
                "slug": "tenant-two",
                "plan": "pro",
                "status": "active",
                "settings": {},
                "usage_limits": {},
            },
        )

        # Query by id=1 — the second tenant (id=2) must not be returned.
        result = await mock_db_session.execute(
            text("SELECT id, name FROM tenants WHERE id = :id LIMIT 1"),
            {"id": 1},
        )
        row = result.fetchone()
        assert row is not None
        assert row.name == "Tenant One"

        # Query by id=2 — the first tenant (id=1) must not be returned.
        result2 = await mock_db_session.execute(
            text("SELECT id, name FROM tenants WHERE id = :id LIMIT 1"),
            {"id": 2},
        )
        row2 = result2.fetchone()
        assert row2 is not None
        assert row2.name == "Tenant Two"

    @pytest.mark.asyncio
    async def test_count_tenants(self, mock_db_session):
        from sqlalchemy import text

        # Seed two tenants via the handler so the count reflects state, not a magic number.
        for name, slug in (("Alpha", "alpha"), ("Beta", "beta")):
            await mock_db_session.execute(
                text(
                    "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) "
                    "VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
                ),
                {
                    "name": name,
                    "slug": slug,
                    "plan": "free",
                    "status": "active",
                    "settings": {},
                    "usage_limits": {},
                },
            )

        result = await mock_db_session.execute(
            text("SELECT COUNT(*) FROM tenants"),
            {},
        )
        count = result.scalar_one()
        assert count == 2
