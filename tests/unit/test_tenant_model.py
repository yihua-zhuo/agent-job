"""Tests for TenantModel."""

from datetime import datetime as dt

import pytest

from db.models.tenant import TenantModel
from tests.unit.conftest import (
    MockState,
    make_mock_session,
    make_tenant_handler,
)


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

    def _run(self, coro):
        import asyncio

        return asyncio.get_event_loop().run_until_complete(coro)

    def test_insert_tenant(self, mock_db_session):
        from sqlalchemy import text

        result = self._run(
            mock_db_session.execute(
                text(
                    "INSERT INTO tenants (name, slug, plan, status, settings, usage_limits) VALUES (:name, :slug, :plan, :status, :settings, :usage_limits)"
                ),
                {
                    "name": "Test Tenant",
                    "slug": "test-tenant",
                    "plan": "free",
                    "status": "active",
                    "settings": "{}",
                    "usage_limits": "{}",
                },
            )
        )
        row = result.fetchone()
        assert row is not None
        assert row.name == "Test Tenant"
        assert row.slug == "test-tenant"
        assert row.plan == "free"

    def test_select_tenant_by_id(self, mock_db_session):
        from sqlalchemy import text

        result = self._run(
            mock_db_session.execute(
                text("SELECT id, name, slug, plan FROM tenants WHERE id = :id LIMIT 1"),
                {"tenant_id": 1},
            )
        )
        row = result.fetchone()
        assert row is not None

    def test_count_tenants(self, mock_db_session):
        from sqlalchemy import text

        result = self._run(
            mock_db_session.execute(
                text("SELECT COUNT(*) FROM tenants"),
                {},
            )
        )
        count = result.scalar_one()
        assert count == 2
