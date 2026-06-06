"""Unit tests for ChurnPredictionService — rule-based real-time scoring."""

from __future__ import annotations

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.churn_prediction_service import ChurnPrediction, ChurnPredictionService, ChurnRiskFactor
from tests.unit.conftest import MockState, make_count_handler, make_customer_handler, make_mock_session


@pytest.fixture
def mock_db_session():
    state = MockState()
    state.customers[1] = {
        "id": 1,
        "tenant_id": 1,
        "name": "Test",
        "email": "test@example.com",
        "phone": None,
        "company": None,
        "status": "lead",
        "owner_id": 1,
        "tags": "[]",
        "created_at": None,
        "updated_at": None,
        "score": None,
        "tier": None,
        "score_factors": None,
        "top_factors": None,
        "recommendations": None,
    }
    return make_mock_session([make_customer_handler(state), make_count_handler(state)], state=state)


@pytest.fixture
def service(mock_db_session):
    return ChurnPredictionService(mock_db_session)


class TestCalculateScore:
    """Happy path — customer exists, all dimensions return data, result is a ChurnPrediction."""

    async def test_returns_dataclass(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert isinstance(result, ChurnPrediction)

    async def test_score_in_range(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert 0.0 <= result.score <= 100.0

    async def test_tier_valid(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert result.tier in ("high", "medium", "low")

    async def test_top_3_risk_factors(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert len(result.top_3_risk_factors) == 3
        for factor in result.top_3_risk_factors:
            assert isinstance(factor, ChurnRiskFactor)
            assert factor.name
            assert isinstance(factor.weight, float)
            assert isinstance(factor.score, float)
            assert factor.description

    async def test_recommended_actions_non_empty(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert isinstance(result.recommended_actions, list)
        assert len(result.recommended_actions) >= 1


class TestCustomerNotFound:
    """Error path — raise NotFoundException when customer does not exist."""

    @pytest.fixture
    def empty_service(self):
        """Service with no SQL handlers — every SELECT returns an empty result."""
        session = make_mock_session([])
        return ChurnPredictionService(session)

    async def test_raises_not_found(self, empty_service):
        with pytest.raises(NotFoundException):
            await empty_service.calculate_score(customer_id=9999, tenant_id=1)

    async def test_wrong_tenant_raises_not_found(self, empty_service):
        with pytest.raises(NotFoundException):
            await empty_service.calculate_score(customer_id=1, tenant_id=999)


class TestReturnTypeContract:
    """Structural — result must be a ChurnPrediction dataclass, not a dict or ApiResponse."""

    async def test_not_dict(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert not isinstance(result, dict)

    async def test_fields_accessible_as_attributes(self, service):
        result = await service.calculate_score(customer_id=1, tenant_id=1)
        assert result.customer_id == 1
        assert hasattr(result, "score")
        assert hasattr(result, "tier")
        assert hasattr(result, "top_3_risk_factors")
        assert hasattr(result, "recommended_actions")


class TestTierBoundaries:
    """Tier mapping contract — exercise the static tier logic directly."""

    def test_high_tier(self):
        assert ChurnPredictionService._compute_tier(70.0) == "high"
        assert ChurnPredictionService._compute_tier(100.0) == "high"
        assert ChurnPredictionService._compute_tier(99.99) == "high"

    def test_medium_tier(self):
        assert ChurnPredictionService._compute_tier(40.0) == "medium"
        assert ChurnPredictionService._compute_tier(69.99) == "medium"

    def test_low_tier(self):
        assert ChurnPredictionService._compute_tier(0.0) == "low"
        assert ChurnPredictionService._compute_tier(39.99) == "low"


class TestNormalizeScore:
    """Sub-score normalization for each dimension."""

    def test_login_frequency_caps_at_100(self):
        assert ChurnPredictionService._normalize_score("login_frequency", 10) == 100
        assert ChurnPredictionService._normalize_score("login_frequency", 5) == 50.0

    def test_purchase_recency_inverts(self):
        assert ChurnPredictionService._normalize_score("purchase_recency", 0) == 100.0
        assert ChurnPredictionService._normalize_score("purchase_recency", 100) == 0.0

    def test_support_ticket_count_caps_at_100(self):
        assert ChurnPredictionService._normalize_score("support_ticket_count", 5) == 100
        assert ChurnPredictionService._normalize_score("support_ticket_count", 3) == 60.0

    def test_engagement_score_caps_at_100(self):
        assert ChurnPredictionService._normalize_score("engagement_score", 30) == 100
        assert ChurnPredictionService._normalize_score("engagement_score", 15) == 50.0
