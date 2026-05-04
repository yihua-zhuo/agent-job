"""Integration tests for intelligence/ML services: ChurnPrediction, SalesRecommendation, SmartCategorization."""
import sys
from pathlib import Path

# Ensure src/ is on sys.path
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest

from services.churn_prediction import ChurnPredictionService
from services.sales_recommendation import SalesRecommendationService
from services.smart_categorization import SmartCategorizationService


class TestChurnPredictionService:
    """Test ChurnPredictionService - churn scoring and risk assessment."""

    @pytest.fixture
    def svc(self):
        return ChurnPredictionService()

    def test_calculate_churn_score_returns_0_to_100(self, svc):
        score = svc.calculate_churn_score(customer_id=1)
        assert 0 <= score <= 100

    def test_score_deterministic(self, svc):
        """Same customer_id always returns same score."""
        s1 = svc.calculate_churn_score(customer_id=42)
        s2 = svc.calculate_churn_score(customer_id=42)
        assert s1 == s2

    def test_score_varies_across_customers(self, svc):
        scores = {svc.calculate_churn_score(cid) for cid in range(1, 50)}
        assert len(scores) > 1

    def test_predict_churn_single_customer(self, svc):
        results = svc.predict_churn(customer_ids=[100])
        assert len(results) == 1
        r = results[0]
        assert r["customer_id"] == 100
        assert "score" in r
        assert "risk_level" in r
        assert "factors" in r
        assert r["risk_level"] in ("low", "medium", "high")

    def test_predict_churn_batch(self, svc):
        results = svc.predict_churn(customer_ids=[1, 2, 3, 4, 5])
        assert len(results) == 5
        for r in results:
            assert r["risk_level"] in ("low", "medium", "high")

    def test_predict_churn_empty_returns_all(self, svc):
        """Default batch returns predictions for customers 1-100."""
        results = svc.predict_churn()
        assert len(results) == 100

    def test_get_churn_risk_factors(self, svc):
        factors = svc.get_churn_risk_factors(customer_id=77)
        assert isinstance(factors, list)
        assert len(factors) == 6
        for f in factors:
            assert "factor" in f
            assert "weight" in f
            assert "current_value" in f
        # Check expected factor names
        names = {f["factor"] for f in factors}
        expected = {
            "days_since_last_activity",
            "decrease_in_activity",
            "decrease_in_revenue",
            "support_tickets_increase",
            "payment_delays",
            "negative_feedback",
        }
        assert names == expected

    def test_get_high_risk_customers(self, svc):
        high_risk = svc.get_high_risk_customers(threshold=70.0)
        assert isinstance(high_risk, list)
        for r in high_risk:
            assert r["score"] >= 70.0
        # Sorted descending
        if len(high_risk) > 1:
            assert high_risk[0]["score"] >= high_risk[1]["score"]

    def test_recommend_actions(self, svc):
        actions = svc.recommend_actions(customer_id=42)
        assert isinstance(actions, list)
        assert len(actions) > 0
        for a in actions:
            assert "action" in a
            assert "priority" in a
            assert a["priority"] in ("high", "medium", "low")

    def test_risk_level_boundaries(self, svc):
        """Verify risk level classification is consistent with score."""
        for cid in range(1, 101):
            score = svc.calculate_churn_score(cid)
            level = svc._get_risk_level(score)
            if score >= 70:
                assert level == "high"
            elif score >= 40:
                assert level == "medium"
            else:
                assert level == "low"


class TestSalesRecommendationService:
    """Test SalesRecommendationService - recommendations and predictions."""

    @pytest.fixture
    def svc(self):
        return SalesRecommendationService()

    def test_get_next_best_action(self, svc):
        result = svc.get_next_best_action(customer_id=1)
        assert "action" in result
        assert "target" in result
        assert "reason" in result
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 1
        assert result["action"] in ("up_sell", "retention", "cross_sell", "maintain")

    def test_next_best_action_returns_valid_action(self, svc):
        result = svc.get_next_best_action(customer_id=42)
        # Deterministic parts: action, target, reason (confidence is random)
        assert result["action"] in ("up_sell", "retention", "cross_sell", "maintain")
        assert isinstance(result["target"], str)
        assert isinstance(result["reason"], str)
        assert 0.6 <= result["confidence"] <= 0.95

    def test_recommend_cross_sell(self, svc):
        recs = svc.recommend_cross_sell(customer_id=99)
        assert isinstance(recs, list)
        assert len(recs) <= 5
        for r in recs:
            assert "product_id" in r
            assert "product_name" in r
            assert "score" in r
            assert 0 <= r["score"] <= 1.0
            assert "reason" in r
            assert r["product_id"] != svc._get_mock_customer_data(99)["current_tier"]

    def test_recommend_cross_sell_returns_valid_structure(self, svc):
        recs = svc.recommend_cross_sell(customer_id=77)
        # Validates structure, not exact order/score (algorithm uses random internals)
        assert isinstance(recs, list)
        assert len(recs) <= 5
        current_tier = svc._get_mock_customer_data(77)["current_tier"]
        for r in recs:
            assert "product_id" in r
            assert "product_name" in r
            assert "score" in r
            assert 0 <= r["score"] <= 1.0
            assert "reason" in r
            assert r["product_id"] != current_tier

    def test_recommend_up_sell(self, svc):
        recs = svc.recommend_up_sell(customer_id=5)
        assert isinstance(recs, list)
        if len(recs) > 0:
            for r in recs:
                assert "product_id" in r
                assert "score" in r
                assert r["score"] <= 1.0

    def test_get_similar_customers(self, svc):
        similar = svc.get_similar_customers(customer_id=33, limit=5)
        assert isinstance(similar, list)
        assert len(similar) <= 5
        for s in similar:
            assert "customer_id" in s
            assert "current_tier" in s
            assert "monthly_revenue" in s

    def test_predict_conversion_probability(self, svc):
        prob = svc.predict_conversion_probability(opportunity_id=1)
        assert 0 <= prob <= 1
        # Deterministic
        prob2 = svc.predict_conversion_probability(opportunity_id=1)
        assert prob == prob2

    def test_product_catalog_integrity(self, svc):
        """All products have required fields."""
        for product_id, info in svc.PRODUCTS.items():
            assert "name" in info
            assert "price" in info
            assert "tier" in info
            assert info["price"] > 0


class TestSmartCategorizationService:
    """Test SmartCategorizationService - lead scoring and customer segmentation."""

    @pytest.fixture
    def svc(self):
        return SmartCategorizationService()

    def test_score_lead(self, svc):
        lead = {
            "source": "referral",
            "company_size": 500,
            "title": "CEO",
            "engaged_actions": ["downloaded_trial", "booked_demo"],
        }
        score = svc.score_lead(lead)
        assert 0 <= score <= 100
        # Referral + 500 employees + CEO + 2 strong actions = should be high
        assert score >= 50

    def test_score_lead_all_zeros(self, svc):
        score = svc.score_lead({})
        assert 0 <= score <= 100

    def test_categorize_lead(self, svc):
        hot_lead = {
            "source": "referral",
            "company_size": 2000,
            "title": "CTO",
            "engaged_actions": ["downloaded_trial", "attended_webinar", "booked_demo"],
        }
        result = svc.categorize_lead(hot_lead)
        assert "category" in result
        assert "score" in result
        assert "reasoning" in result
        assert result["category"] in ("hot_lead", "warm_lead", "cold_lead", "disqualified")

    def test_categorize_lead_score_boundaries(self, svc):
        # Hot lead - score >= 75
        hot = {
            "source": "referral", "company_size": 1000, "title": "CEO",
            "engaged_actions": ["downloaded_trial", "booked_demo"],
        }
        assert svc.score_lead(hot) >= 75

        # Disqualified - score < 25
        cold = {"source": "cold_outreach", "company_size": 5, "title": "intern"}
        assert svc.score_lead(cold) < 25

    def test_auto_tag_customer(self, svc):
        tags = svc.auto_tag_customer(customer_id=1)
        assert isinstance(tags, list)
        assert len(tags) >= 4  # Based on multiple tag categories
        # Tags should be strings
        for t in tags:
            assert isinstance(t, str)

    def test_auto_tag_deterministic(self, svc):
        t1 = svc.auto_tag_customer(customer_id=42)
        t2 = svc.auto_tag_customer(customer_id=42)
        assert t1 == t2

    def test_segment_customers(self, svc):
        segments = svc.segment_customers()
        assert isinstance(segments, list)
        assert len(segments) == 500
        for seg in segments:
            assert "customer_id" in seg
            assert "segment" in seg
            assert "rfm_total" in seg
            assert seg["segment"] in ("VIP", "Active", "AtRisk", "Dormant")

    def test_segment_vip_high_rfm(self, svc):
        """Customer with RFM total >= 12 should be VIP."""
        segments = svc.segment_customers()
        vip = [s for s in segments if s["segment"] == "VIP"]
        for v in vip:
            assert v["rfm_total"] >= 12
