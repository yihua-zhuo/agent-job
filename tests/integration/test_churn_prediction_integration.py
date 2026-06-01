"""
Integration tests for ChurnPrediction model.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_churn_prediction_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from db.models.churn_prediction import ChurnPredictionModel
from db.models.tenant import TenantModel


# ── Seed tenants and customers so FK constraints on churn_predictions are satisfied ──
@pytest_asyncio.fixture(scope="function", autouse=True)
async def _seed_tenant(async_session, tenant_id: int) -> int:
    from db.models.customer import CustomerModel

    tenant = TenantModel(id=tenant_id, name="Churn Integration Test Tenant", plan="free", status="active")
    async_session.add(tenant)
    await async_session.flush()
    for cid in range(1, 201):
        customer = CustomerModel(id=cid, tenant_id=tenant_id, name=f"Churn Customer {cid}", email=f"churn_cust{cid}@test.example.com", status="active")
        async_session.add(customer)
    await async_session.flush()
    return tenant_id


@pytest_asyncio.fixture(scope="function", autouse=True)
async def _seed_tenant_2(async_session, tenant_id_2: int) -> int:
    from db.models.customer import CustomerModel

    tenant = TenantModel(id=tenant_id_2, name="Churn Integration Test Tenant 2", plan="free", status="active")
    async_session.add(tenant)
    await async_session.flush()
    for cid in range(201, 401):
        customer = CustomerModel(id=cid, tenant_id=tenant_id_2, name=f"Churn Customer 2 {cid}", email=f"churn_cust2_{cid}@test.example.com", status="active")
        async_session.add(customer)
    await async_session.flush()
    return tenant_id_2


@pytest.mark.integration
class TestChurnPredictionIntegration:
    """Full ChurnPrediction lifecycle via the real DB."""

    async def test_insert_and_query(self, db_schema, tenant_id, async_session):
        """Insert a churn prediction and query it back."""
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=1,
            score=0.85,
            tier="high",
            factors=["low_engagement", "support_tickets_up"],
        )
        async_session.add(pred)
        await async_session.flush()
        await async_session.commit()

        from sqlalchemy import select

        result = await async_session.execute(
            select(ChurnPredictionModel).where(
                ChurnPredictionModel.tenant_id == tenant_id,
                ChurnPredictionModel.customer_id == 1,
            )
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert fetched.customer_id == 1
        assert fetched.score == 0.85
        assert fetched.tier == "high"
        assert "low_engagement" in fetched.factors

    async def test_to_dict_after_insert(self, db_schema, tenant_id, async_session):
        """to_dict() returns correct values after persistence."""
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=2,
            score=0.42,
            tier="low",
            factors=[" infrequent_purchase"],
        )
        async_session.add(pred)
        await async_session.commit()

        d = pred.to_dict()
        assert d["tenant_id"] == tenant_id
        assert d["customer_id"] == 2
        assert d["score"] == 0.42
        assert d["tier"] == "low"
        assert d["factors"] == [" infrequent_purchase"]
        assert d["predicted_at"] is not None
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    async def test_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Predictions are isolated by tenant_id."""
        pred1 = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=10,
            score=0.9,
        )
        pred2 = ChurnPredictionModel(
            tenant_id=tenant_id_2,
            customer_id=10,
            score=0.1,
        )
        async_session.add(pred1)
        async_session.add(pred2)
        await async_session.commit()

        from sqlalchemy import select

        result = await async_session.execute(
            select(ChurnPredictionModel).where(
                ChurnPredictionModel.tenant_id == tenant_id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].score == 0.9
