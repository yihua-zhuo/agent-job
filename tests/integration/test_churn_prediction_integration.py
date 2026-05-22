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
    """ChurnPrediction table lifecycle via the real DB."""

    async def test_insert_and_fetch(self, db_schema, tenant_id, async_session, _seed_customer):
        """Insert a ChurnPrediction row and retrieve it with all fields correct."""
        customer_id = _seed_customer

        prediction = ChurnPredictionModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=85,
            tier="high",
            factors=[
                {"name": "low_engagement", "weight": 0.6},
                {"name": "high_churn_risk_flag", "weight": 0.4},
            ],
            recommended_actions=[
                {"action": "send_retention_email", "priority": "high"},
                {"action": "offer_discount", "priority": "medium"},
            ],
            model_version="churn-v2.1",
        )
        async_session.add(prediction)
        await async_session.commit()
        await async_session.refresh(prediction)

        assert prediction.id is not None
        assert prediction.tenant_id == tenant_id
        assert prediction.customer_id == customer_id
        assert prediction.score == 85
        assert prediction.tier == "high"
        assert len(prediction.factors) == 2
        assert prediction.factors[0]["name"] == "low_engagement"
        assert len(prediction.recommended_actions) == 2
        assert prediction.recommended_actions[0]["action"] == "send_retention_email"
        assert prediction.model_version == "churn-v2.1"
        assert prediction.created_at is not None
