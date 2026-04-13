"""Unit tests for ChurnPredictionService."""
import pytest
from src.services.churn_prediction import ChurnPredictionService


@pytest.fixture
def churn_service():
    return ChurnPredictionService()


@pytest.mark.asyncio
class TestChurnPredictionNormal:
    async def test_calculate_churn_score(self, churn_service):
        score = await churn_service.calculate_churn_score(1)
        assert 0 <= score <= 100
        assert isinstance(score, float)

    async def test_predict_churn_single_customer(self, churn_service):
        results = await churn_service.predict_churn([1, 2, 3])
        assert len(results) == 3
        for r in results:
            assert "customer_id" in r
            assert "score" in r
            assert "risk_level" in r
            assert "factors" in r

    async def test_predict_churn_with_threshold(self, churn_service):
        results = await churn_service.predict_churn(customer_ids=[1, 50, 100])
        for r in results:
            assert r["risk_level"] in ["low", "medium", "high"]

    async def test_get_churn_risk_factors(self, churn_service):
        factors = await churn_service.get_churn_risk_factors(1)
        assert len(factors) == 6
        for f in factors:
            assert "factor" in f
            assert "weight" in f
            assert "current_value" in f

    async def test_get_high_risk_customers(self, churn_service):
        high_risk = await churn_service.get_high_risk_customers(threshold=70.0)
        for c in high_risk:
            assert c["score"] >= 70.0

    async def test_recommend_actions_basic(self, churn_service):
        actions = await churn_service.recommend_actions(1)
        assert len(actions) > 0
        for action in actions:
            assert "action" in action
            assert "priority" in action
            assert "reason" in action


@pytest.mark.asyncio
class TestChurnPredictionEdgeCases:
    async def test_calculate_churn_score_different_customers(self, churn_service):
        score1 = await churn_service.calculate_churn_score(1)
        score2 = await churn_service.calculate_churn_score(2)
        assert 0 <= score1 <= 100
        assert 0 <= score2 <= 100

    async def test_calculate_churn_score_large_id(self, churn_service):
        score = await churn_service.calculate_churn_score(999999)
        assert 0 <= score <= 100

    async def test_calculate_churn_score_zero_id(self, churn_service):
        score = await churn_service.calculate_churn_score(0)
        assert 0 <= score <= 100

    async def test_predict_churn_empty_list(self, churn_service):
        results = await churn_service.predict_churn([])
        assert len(results) == 0

    async def test_predict_churn_none(self, churn_service):
        results = await churn_service.predict_churn(customer_ids=None)
        assert len(results) > 0

    async def test_predict_churn_duplicate_ids(self, churn_service):
        results = await churn_service.predict_churn([1, 1, 2])
        assert len(results) >= 2

    async def test_get_churn_risk_factors_all_factors_present(self, churn_service):
        factors = await churn_service.get_churn_risk_factors(42)
        factor_names = [f["factor"] for f in factors]
        expected_factors = [
            "days_since_last_activity",
            "decrease_in_activity",
            "decrease_in_revenue",
            "support_tickets_increase",
            "payment_delays",
            "negative_feedback",
        ]
        for ef in expected_factors:
            assert ef in factor_names

    async def test_get_churn_risk_factors_weights_sum(self, churn_service):
        factors = await churn_service.get_churn_risk_factors(1)
        total_weight = sum(f["weight"] for f in factors)
        assert abs(total_weight - 1.0) < 0.01

    async def test_get_high_risk_customers_no_matches(self, churn_service):
        high_risk = await churn_service.get_high_risk_customers(threshold=100.0)
        assert isinstance(high_risk, list)

    async def test_get_high_risk_customers_low_threshold(self, churn_service):
        high_risk = await churn_service.get_high_risk_customers(threshold=0.0)
        assert len(high_risk) > 0

    async def test_recommend_actions_for_new_customer(self, churn_service):
        actions = await churn_service.recommend_actions(1)
        high_priority = [a for a in actions if a["priority"] == "high"]
        assert len(high_priority) <= 3

    async def test_recommend_actions_for_high_risk_customer(self, churn_service):
        high_risk = await churn_service.get_high_risk_customers(threshold=80.0)
        if high_risk:
            actions = await churn_service.recommend_actions(high_risk[0]["customer_id"])
            assert len(actions) > 0

    async def test_risk_level_boundaries(self, churn_service):
        assert churn_service._get_risk_level(0) == "low"
        assert churn_service._get_risk_level(39.99) == "low"
        assert churn_service._get_risk_level(40) == "medium"
        assert churn_service._get_risk_level(69.99) == "medium"
        assert churn_service._get_risk_level(70) == "high"
        assert churn_service._get_risk_level(100) == "high"

    async def test_risk_factors_deterministic(self, churn_service):
        factors1 = await churn_service.get_churn_risk_factors(123)
        factors2 = await churn_service.get_churn_risk_factors(123)
        for f1, f2 in zip(factors1, factors2):
            assert f1["factor"] == f2["factor"]
            assert f1["current_value"] == f2["current_value"]

    async def test_churn_score_deterministic(self, churn_service):
        score1 = await churn_service.calculate_churn_score(456)
        score2 = await churn_service.calculate_churn_score(456)
        assert score1 == score2
