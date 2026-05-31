"""
Integration tests for ChurnPrediction model.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_churn_prediction_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest

from db.models.churn_prediction import ChurnPredictionModel, ChurnTier


async def _seed_customer(async_session, tenant_id: int) -> int:
    """Create a customer and return its id."""
    from db.models.customer import CustomerModel

    customer = CustomerModel(
        tenant_id=tenant_id,
        name="Churn Test Customer",
        email="churn-test@example.com",
        status="active",
    )
    async_session.add(customer)
    await async_session.flush()
    return customer.id


@pytest.mark.integration
class TestChurnPredictionIntegration:
    """ChurnPrediction table lifecycle via the real DB."""

    async def test_insert_and_fetch(self, db_schema, tenant_id, async_session):
        """Insert a ChurnPrediction row and retrieve it with all fields correct."""
        customer_id = await _seed_customer(async_session, tenant_id)

        prediction = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=85,
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
        assert prediction.score == 85
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
        customer_id = await _seed_customer(async_session, tenant_id)
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=85,
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
        assert fetched.score == 85
        assert fetched.tier == ChurnTier.high
        assert fetched.factors[0]["name"] == "low_engagement"

    async def test_to_dict_after_insert(self, db_schema, tenant_id, async_session):
        """to_dict() returns correct values after persistence."""
        customer_id = await _seed_customer(async_session, tenant_id)
        pred = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=42,
            tier=ChurnTier.low,
            factors=[{"name": "infrequent_purchase", "weight": 0.7, "explanation": "Purchase frequency dropped"}],
        )
        async_session.add(pred)
        await async_session.commit()

        d = pred.to_dict()
        assert d["tenant_id"] == tenant_id
        assert d["customer_id"] == customer_id
        assert d["score"] == 42
        assert d["tier"] == "low"
        assert d["factors"][0]["name"] == "infrequent_purchase"
        assert d["predicted_at"] is not None
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    async def test_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Predictions are isolated by tenant_id."""
        customer_id_1 = await _seed_customer(async_session, tenant_id)
        customer_id_2 = await _seed_customer(async_session, tenant_id_2)
        pred1 = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id_1,
            score=90,
            tier=ChurnTier.high,
            factors=[],
            recommended_actions=[],
        )
        pred2 = ChurnPredictionModel(
            tenant_id=tenant_id_2,
            customer_id=customer_id_2,
            score=10,
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
        assert rows[0].score == 90
