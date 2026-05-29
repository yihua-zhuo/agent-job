"""Integration tests for TenantModel — uses real PostgreSQL."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
class TestTenantIntegration:
    async def test_insert_and_select_tenant_with_slug_and_usage_limits(
        self, db_schema, tenant_id, async_session
    ):
        from db.models.tenant import TenantModel

        now = datetime.now(timezone.utc)
        tenant = TenantModel(
            id=tenant_id,
            name="Integration Test Tenant",
            slug="integration-test",
            plan="pro",
            status="active",
            settings={"theme": "light"},
            usage_limits={"users": 25, "storage_gb": 50},
            created_at=now,
            updated_at=now,
        )
        async_session.add(tenant)
        await async_session.commit()

        result = await async_session.get(TenantModel, tenant_id)
        assert result is not None
        assert result.name == "Integration Test Tenant"
        assert result.slug == "integration-test"
        assert result.plan == "pro"
        assert result.status == "active"
        assert result.settings == {"theme": "light"}
        assert result.usage_limits == {"users": 25, "storage_gb": 50}

    async def test_tenant_slug_not_null_constraint(self, db_schema, tenant_id):
        """Verify that inserting NULL slug raises an IntegrityError.

        Uses a direct psycopg2 connection so the fixture session rollback does not
        suppress the constraint error before assertion runs.
        """
        from tests.integration.conftest import _get_test_sync_engine

        sync_engine = _get_test_sync_engine()
        Session = sessionmaker(bind=sync_engine, autoflush=True, autocommit=False)
        session = Session()
        now = datetime.now(timezone.utc)
        try:
            session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                    VALUES (:id, :name, :slug, :plan, :status, '{}', '{}', :created_at, :updated_at)
                """),
                {
                    "id": tenant_id,
                    "name": "Null Slug",
                    "slug": None,
                    "plan": "free",
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            session.commit()
        except IntegrityError:
            return
        finally:
            session.close()
        pytest.fail("IntegrityError was not raised for NULL slug")

    async def test_tenant_usage_limits_not_null_constraint(self, db_schema, tenant_id):
        """Verify that inserting NULL usage_limits raises an IntegrityError."""
        from tests.integration.conftest import _get_test_sync_engine

        sync_engine = _get_test_sync_engine()
        Session = sessionmaker(bind=sync_engine, autoflush=True, autocommit=False)
        session = Session()
        now = datetime.now(timezone.utc)
        try:
            session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                    VALUES (:id, :name, :slug, :plan, :status, '{}', :usage_limits, :created_at, :updated_at)
                """),
                {
                    "id": tenant_id,
                    "name": "Null Limits",
                    "slug": "null-limits",
                    "plan": "free",
                    "status": "active",
                    "usage_limits": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            session.commit()
        except IntegrityError:
            return
        finally:
            session.close()
        pytest.fail("IntegrityError was not raised for NULL usage_limits")

    async def test_tenant_default_slug_applied_when_omitted(
        self, db_schema, tenant_id, async_session
    ):
        from db.models.tenant import TenantModel

        now = datetime.now(timezone.utc)
        tenant = TenantModel(
            id=tenant_id,
            name="Default Slug Tenant",
            plan="free",
            status="active",
            created_at=now,
            updated_at=now,
        )
        async_session.add(tenant)
        await async_session.commit()

        result = await async_session.get(TenantModel, tenant_id)
        assert result is not None
        assert result.slug == ""

    async def test_tenant_accepts_explicit_empty_slug(
        self, db_schema, tenant_id, async_session
    ):
        from db.models.tenant import TenantModel

        now = datetime.now(timezone.utc)
        tenant = TenantModel(
            id=tenant_id,
            name="Explicit Empty Slug Tenant",
            slug="",
            plan="free",
            status="active",
            settings={},
            usage_limits={},
            created_at=now,
            updated_at=now,
        )
        async_session.add(tenant)
        await async_session.commit()

        result = await async_session.get(TenantModel, tenant_id)
        assert result is not None
        assert result.slug == ""
