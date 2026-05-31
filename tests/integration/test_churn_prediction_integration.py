"""
Integration tests for ChurnPrediction model.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_churn_prediction_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest

from db.models.churn_prediction import ChurnPredictionModel


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
