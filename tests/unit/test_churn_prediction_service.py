"""Unit tests for ChurnPredictionService — rule-based real-time scoring."""

from __future__ import annotations

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.churn_prediction_service import ChurnPrediction, ChurnPredictionService, ChurnRiskFactor
from tests.unit.conftest import (
    MockResult,
    MockRow,
    MockState,
    make_count_handler,
    make_customer_handler,
    make_mock_session,
)


def _seed_test_customer(state: MockState, customer_id: int = 1, tenant_id: int = 1) -> None:
    state.customers[customer_id] = {
        "id": customer_id,
        "tenant_id": tenant_id,
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


def _make_tenant_aware_customer_handler(state: MockState):
    """Customer handler that filters by tenant_id in the SQL predicate.

    The shared ``make_customer_handler`` only matches ``from customers where id`` and ignores
    tenant_id, which would mask cross-tenant isolation bugs. This handler inspects the
    tenant_id param and only returns the customer when it matches the seeded record.
    """

    def handler(sql_text, params):
        normalized = " ".join(sql_text.split())
        if "from customers where" in normalized and "customers.id" in normalized:
            # SQLAlchemy bind params are suffixed (_1, _2, ...). Accept either form.
            customer_id = params.get("id") if "id" in params else params.get("id_1")
            tenant_id = params.get("tenant_id") if "tenant_id" in params else params.get("tenant_id_1")
            if customer_id in state.customers:
                rec = state.customers[customer_id]
                if tenant_id is None or rec.get("tenant_id") == tenant_id:
                    return MockResult([MockRow(rec.copy())])
                return MockResult([])
            return MockResult([])
        return None

    return handler


@pytest.fixture
def mock_db_session():
    state = MockState()
    _seed_test_customer(state, customer_id=1, tenant_id=1)
    return make_mock_session(
        [_make_tenant_aware_customer_handler(state), make_customer_handler(state), make_count_handler(state)],
        state=state,
    )


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
    """Error path — raise NotFoundException when customer does not exist or belongs to a different tenant."""

    @pytest.fixture
    def tenant_isolated_service(self):
        """Service with a tenant-aware customer handler wired to seeded state.

        The handler returns the customer only when tenant_id matches the seeded record,
        so a wrong-tenant request is rejected by the SQL predicate (not by a bare empty
        session). This proves the service's tenant filter is what excludes the row.
        """
        state = MockState()
        _seed_test_customer(state, customer_id=1, tenant_id=1)
        session = make_mock_session(
            [_make_tenant_aware_customer_handler(state), make_count_handler(state)],
            state=state,
        )
        return ChurnPredictionService(session)

    async def test_raises_not_found_when_customer_missing(self, tenant_isolated_service):
        with pytest.raises(NotFoundException):
            await tenant_isolated_service.calculate_score(customer_id=9999, tenant_id=1)

    async def test_wrong_tenant_raises_not_found(self, tenant_isolated_service):
        # Customer 1 is seeded under tenant_id=1 — querying with tenant_id=999 must be
        # rejected by the tenant predicate, not by an empty mock state.
        with pytest.raises(NotFoundException):
            await tenant_isolated_service.calculate_score(customer_id=1, tenant_id=999)


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
