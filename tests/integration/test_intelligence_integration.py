"""Integration tests for intelligence/ML services: ChurnPrediction, SalesRecommendation, SmartCategorization."""
import sys
import uuid
from pathlib import Path

# Ensure src/ is on sys.path
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.churn_prediction import ChurnPredictionService
from services.customer_service import CustomerService
from services.sales_recommendation import SalesRecommendationService
from services.smart_categorization import SmartCategorizationService


async def _seed_customer(async_session, tenant_id: int) -> int:
    """Seed a customer and return its id."""
    svc = CustomerService(async_session)
    suffix = uuid.uuid4().hex[:8]
    result = await svc.create_customer(
        data={
            "name": f"Churn Cust {suffix}",
            "email": f"churn_{suffix}@example.com",
            "phone": "13800138000",
            "status": "lead",
        },
        tenant_id=tenant_id,
    )
    return result.id


@pytest.mark.integration
class TestChurnPredictionService:
    """Test ChurnPredictionService - DB-backed churn scoring."""

    async def test_calculate_churn_score_returns_0_to_100(self, db_schema, tenant_id, async_session):
        cid = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        score = await svc.calculate_churn_score(customer_id=cid, tenant_id=tenant_id)
        assert 0 <= score <= 100

    async def test_score_deterministic(self, db_schema, tenant_id, async_session):
        """Same customer + same data → same score."""
        cid = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        s1 = await svc.calculate_churn_score(customer_id=cid, tenant_id=tenant_id)
        s2 = await svc.calculate_churn_score(customer_id=cid, tenant_id=tenant_id)
        assert s1 == s2

    async def test_calculate_churn_score_not_found(self, db_schema, tenant_id, async_session):
        svc = ChurnPredictionService(async_session)
        with pytest.raises(NotFoundException):
            await svc.calculate_churn_score(customer_id=999_999_999, tenant_id=tenant_id)

    async def test_predict_churn_single_customer(self, db_schema, tenant_id, async_session):
        cid = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        results = await svc.predict_churn(customer_ids=[cid], tenant_id=tenant_id)
        assert len(results) == 1
        r = results[0]
        assert r["customer_id"] == cid
        assert "score" in r
        assert r["risk_level"] in ("low", "medium", "high")

    async def test_predict_churn_batch(self, db_schema, tenant_id, async_session):
        ids = [await _seed_customer(async_session, tenant_id) for _ in range(3)]
        svc = ChurnPredictionService(async_session)
        results = await svc.predict_churn(customer_ids=ids, tenant_id=tenant_id)
        assert len(results) == 3
        for r in results:
            assert r["risk_level"] in ("low", "medium", "high")

    async def test_predict_churn_default_lists_tenant_customers(self, db_schema, tenant_id, async_session):
        """Default (no ids) returns predictions for all tenant customers."""
        for _ in range(2):
            await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        results = await svc.predict_churn(tenant_id=tenant_id)
        assert len(results) >= 2

    async def test_get_churn_risk_factors(self, db_schema, tenant_id, async_session):
        cid = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        factors = await svc.get_churn_risk_factors(customer_id=cid, tenant_id=tenant_id)
        assert isinstance(factors, list)
        assert len(factors) == 6
        names = {f["factor"] for f in factors}
        assert names == {
            "days_since_last_activity",
            "decrease_in_activity",
            "decrease_in_revenue",
            "support_tickets_increase",
            "payment_delays",
            "negative_feedback",
        }

    async def test_get_high_risk_customers(self, db_schema, tenant_id, async_session):
        for _ in range(3):
            await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        high_risk = await svc.get_high_risk_customers(threshold=0.0, tenant_id=tenant_id)
        assert isinstance(high_risk, list)
        # Sorted descending
        if len(high_risk) > 1:
            assert high_risk[0]["score"] >= high_risk[1]["score"]

    async def test_recommend_actions(self, db_schema, tenant_id, async_session):
        cid = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session)
        actions = await svc.recommend_actions(customer_id=cid, tenant_id=tenant_id)
        assert isinstance(actions, list)
        assert len(actions) > 0
        for a in actions:
            assert a["priority"] in ("high", "medium", "low")


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
