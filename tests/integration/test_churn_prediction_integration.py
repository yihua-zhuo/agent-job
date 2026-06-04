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

from db.models.churn_prediction import ChurnPredictionModel, ChurnTier
from tests.integration.domain_fixtures.churn_prediction import seed_churn_customer


# Tests that need a seeded tenant must request this fixture explicitly.
# Cross-tenant tests additionally request `_seed_tenant_2`.
@pytest_asyncio.fixture(scope="function", autouse=True)
async def _seed_tenant(async_session, tenant_id: int) -> int:
    """Seed the primary tenant for all tests in this module."""
    from db.models.tenant import TenantModel

    tenant = TenantModel(
        id=tenant_id,
        name="Churn Integration Test Tenant",
        plan="free",
        status="active",
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant_id


@pytest_asyncio.fixture(scope="function")
async def _seed_tenant_2(async_session, tenant_id_2: int) -> int:
    """Seed a second tenant for cross-tenant isolation tests. Opt-in only."""
    from db.models.tenant import TenantModel

    tenant = TenantModel(
        id=tenant_id_2,
        name="Churn Integration Test Tenant 2",
        plan="free",
        status="active",
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant_id_2


@pytest.mark.integration
class TestChurnPredictionIntegration:
    """ChurnPrediction table lifecycle via the real DB."""

    async def test_insert_and_fetch(self, db_schema, tenant_id, async_session):
        """Insert a ChurnPrediction row and retrieve it with all fields correct."""
        customer_id = await seed_churn_customer(async_session, tenant_id)

        prediction = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=85.0,
            tier=ChurnTier.high,
            factors=[
                {
                    "name": "low_engagement",
                    "weight": 0.6,
                    "explanation": "No activity in the last 30 days",
                },
                {
                    "name": "high_churn_risk_flag",
                    "weight": 0.4,
                    "explanation": "Multiple cancellation signals detected",
                },
            ],
            recommended_actions=[
                {"action": "send_retention_email", "priority": "high"},
                {"action": "offer_discount", "priority": "medium"},
            ],
            model_version="churn-v2.1",
        )
        async_session.add(prediction)
        await async_session.flush()
        await async_session.refresh(prediction)

        assert prediction.id is not None
        assert prediction.tenant_id == tenant_id
        assert prediction.customer_id == customer_id
        assert prediction.score == 85.0
        assert prediction.tier == ChurnTier.high
        assert len(prediction.factors) == 2
        assert prediction.factors[0]["name"] == "low_engagement"
        assert "explanation" in prediction.factors[0]
        assert prediction.factors[0]["explanation"] == "No activity in the last 30 days"
        assert len(prediction.recommended_actions) == 2
        assert prediction.recommended_actions[0]["action"] == "send_retention_email"
        assert prediction.model_version == "churn-v2.1"
        assert prediction.created_at is not None

    async def test_insert_and_query(self, db_schema, tenant_id, async_session):
        """Insert a churn prediction and query it back."""
        customer_id = await seed_churn_customer(async_session, tenant_id)
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=85.0,
            tier=ChurnTier.high,
            factors=[
                {"name": "low_engagement", "weight": 0.6, "explanation": "No activity in 30 days"},
                {"name": "support_tickets_up", "weight": 0.4, "explanation": "Tickets increased"},
            ],
        )
        async_session.add(pred)
        await async_session.flush()
        await async_session.commit()

        from sqlalchemy import select

        result = await async_session.execute(
            select(ChurnPredictionModel).where(
                ChurnPredictionModel.tenant_id == tenant_id,
                ChurnPredictionModel.customer_id == customer_id,
            )
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert fetched.customer_id == customer_id
        assert fetched.score == 85.0
        assert fetched.tier == ChurnTier.high
        assert fetched.factors[0]["name"] == "low_engagement"

    async def test_to_dict_after_insert(self, db_schema, tenant_id, async_session):
        """to_dict() returns correct values after persistence."""
        customer_id = await seed_churn_customer(async_session, tenant_id)
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=42.0,
            tier=ChurnTier.low,
            factors=[{"name": "infrequent_purchase", "weight": 0.7, "explanation": "Purchase frequency dropped"}],
        )
        async_session.add(pred)
        await async_session.flush()

        d = pred.to_dict()
        assert d["tenant_id"] == tenant_id
        assert d["customer_id"] == customer_id
        assert d["score"] == 42.0
        assert d["tier"] == "low"
        assert d["factors"][0]["name"] == "infrequent_purchase"
        assert d["predicted_at"] is not None
        assert d["created_at"] is not None
        assert d["updated_at"] is not None
        assert d["updated_at"] == d["created_at"]  # both use server_default=func.now() on insert

    async def test_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2, async_session, _seed_tenant_2
    ):
        """Predictions are isolated by tenant_id."""
        customer_id_1 = await seed_churn_customer(async_session, tenant_id)
        customer_id_2 = await seed_churn_customer(async_session, tenant_id_2)
        pred1 = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id_1,
            score=90.0,
            tier=ChurnTier.high,
            factors=[],
            recommended_actions=[],
        )
        pred2 = ChurnPredictionModel(
            tenant_id=tenant_id_2,
            customer_id=customer_id_2,
            score=10.0,
            tier=ChurnTier.low,
            factors=[],
            recommended_actions=[],
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
        assert rows[0].score == 90.0

    async def test_score_out_of_range_rejected(self, db_schema, tenant_id, async_session):
        """score=150 violates the 0..100 CheckConstraint at the database level."""
        from sqlalchemy.exc import IntegrityError

        customer_id = await seed_churn_customer(async_session, tenant_id)
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=150.0,
            tier=ChurnTier.high,
            factors=[],
            recommended_actions=[],
        )
        async_session.add(pred)
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()

    async def test_invalid_tier_rejected(self, db_schema, tenant_id, async_session):
        """tier='invalid' violates the PostgreSQL enum at the database level."""
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError

        customer_id = await seed_churn_customer(async_session, tenant_id)
        # Commit the customer seed before the raw-SQL insert: the raw `text()`
        # INSERT runs in a separate autobegin transaction that may not see
        # uncommitted ORM inserts from the same session, so the customer FK
        # row must be visible to the database at COMMIT time.
        await async_session.commit()
        with pytest.raises(DBAPIError):
            await async_session.execute(
                text(
                    "INSERT INTO churn_predictions "
                    "(tenant_id, customer_id, score, tier, factors, recommended_actions) "
                    "VALUES (:tid, :cid, :score, :tier, '[]'::jsonb, '[]'::jsonb)"
                ),
                {
                    "tid": tenant_id,
                    "cid": customer_id,
                    "score": 50.0,
                    "tier": "invalid",
                },
            )
        await async_session.rollback()
