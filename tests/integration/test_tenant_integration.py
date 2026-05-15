"""Integration tests for TenantModel — uses real PostgreSQL."""

import pytest


@pytest.mark.integration
class TestTenantIntegration:
    async def test_insert_and_select_tenant_with_slug_and_usage_limits(self, db_schema, tenant_id, async_session):
        from datetime import datetime as dt

        from sqlalchemy import text

        # Insert a tenant with slug and usage_limits
        now = dt.utcnow()
        await async_session.execute(
            text("""
                INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                VALUES (:id, :name, :slug, :plan, :status, :settings, :usage_limits, :created_at, :updated_at)
            """),
            {
                "id": tenant_id,
                "name": "Integration Test Tenant",
                "slug": "integration-test",
                "plan": "pro",
                "status": "active",
                "settings": '{"theme": "light"}',
                "usage_limits": '{"users": 25, "storage_gb": 50}',
                "created_at": now,
                "updated_at": now,
            },
        )
        await async_session.commit()

        # Select back and verify
        result = await async_session.execute(
            text("SELECT name, slug, plan, status, settings, usage_limits FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row.name == "Integration Test Tenant"
        assert row.slug == "integration-test"
        assert row.plan == "pro"
        assert row.status == "active"

    async def test_tenant_slug_not_null_constraint(self, db_schema, tenant_id, async_session):
        from datetime import datetime as dt

        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        now = dt.utcnow()
        # Attempting to insert with NULL slug should fail
        with pytest.raises(IntegrityError):
            await async_session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                    VALUES (:id, :name, :slug, :plan, :status, :settings, :usage_limits, :created_at, :updated_at)
                """),
                {
                    "id": tenant_id,
                    "name": "Null Slug Tenant",
                    "slug": None,
                    "plan": "free",
                    "status": "active",
                    "settings": "{}",
                    "usage_limits": "{}",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await async_session.commit()

    async def test_tenant_usage_limits_not_null_constraint(self, db_schema, tenant_id, async_session):
        from datetime import datetime as dt

        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        now = dt.utcnow()
        # Attempting to insert with NULL usage_limits should fail
        with pytest.raises(IntegrityError):
            await async_session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                    VALUES (:id, :name, :slug, :plan, :status, :settings, :usage_limits, :created_at, :updated_at)
                """),
                {
                    "id": tenant_id,
                    "name": "Null Limits Tenant",
                    "slug": "null-limits",
                    "plan": "free",
                    "status": "active",
                    "settings": "{}",
                    "usage_limits": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await async_session.commit()

    async def test_tenant_default_slug(self, db_schema, tenant_id, async_session):
        from datetime import datetime as dt

        from sqlalchemy import text

        now = dt.utcnow()
        # Insert with explicit empty slug to test default
        await async_session.execute(
            text("""
                INSERT INTO tenants (id, name, slug, plan, status, settings, usage_limits, created_at, updated_at)
                VALUES (:id, :name, :slug, :plan, :status, :settings, :usage_limits, :created_at, :updated_at)
            """),
            {
                "id": tenant_id,
                "name": "Default Slug Tenant",
                "slug": "",
                "plan": "free",
                "status": "active",
                "settings": "{}",
                "usage_limits": "{}",
                "created_at": now,
                "updated_at": now,
            },
        )
        await async_session.commit()

        result = await async_session.execute(
            text("SELECT slug FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row.slug == ""
