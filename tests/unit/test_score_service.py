"""Unit tests for ScoreService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.score import ScoreTier
from pkg.errors.app_exceptions import NotFoundException
from services.score_service import FIELD_RECOMMENDATIONS, ScoreService
from tests.unit.conftest import MockResult, MockRow, MockState, make_mock_session

CUSTOMER_ID = 1
TENANT_ID = 10
OTHER_TENANT_ID = 99


def _make_session(state: MockState) -> object:
    """Build a mock session that inspects bind params for tenant + customer IDs.

    The handler reads ``params['id']`` and ``params['tenant_id']`` and only
    returns the seeded row when both match. This means a service that drops
    the ``tenant_id`` WHERE clause (cross-tenant data leak) or queries a
    different customer ID will see an empty result, so the service must
    raise NotFoundException. Tests that violate the multi-tenant contract
    fail instead of silently passing.
    """

    def handler(sql_text, params):
        if "from customers" in sql_text and "where" in sql_text:
            # SQLAlchemy Core appends a numeric suffix to bound param names
            # (e.g. id_1, tenant_id_1); accept either form for robustness.
            requested_tenant = params.get("tenant_id", params.get("tenant_id_1"))
            requested_customer = params.get("id", params.get("id_1"))
            if requested_customer is None or requested_customer not in state.customers:
                return MockResult(rows=[])
            record = state.customers[requested_customer]
            # Verify the persisted tenant_id matches the requested one — a
            # cross-tenant lookup (record.tenant_id != requested_tenant) means
            # the service must not see this row.
            if record.get("tenant_id") != requested_tenant:
                return MockResult(rows=[])
            return MockResult(rows=[MockRow(record.copy())])
        return None

    return make_mock_session(handlers=[handler], state=state)


def _seed_customer(state: MockState, score_factors: dict | None) -> None:
    state.customers[CUSTOMER_ID] = {
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": score_factors,
    }


@pytest.fixture
def score_service():
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 90,
            "deal_velocity": 85,
            "support_health": 80,
            "payment_history": 75,
            "product_adoption": 70,
        },
    )
    return ScoreService(_make_session(state))


# (score_factors, expected_tier, score_lower_bound_inclusive)
TIER_CASES: list[tuple[dict | None, str | tuple[str, ...], int]] = [
    (
        {
            "engagement_level": 90,
            "deal_velocity": 85,
            "support_health": 80,
            "payment_history": 75,
            "product_adoption": 70,
        },
        ScoreTier.A.value,
        80,
    ),
    (
        {
            "engagement_level": 5,
            "deal_velocity": 10,
            "support_health": 0,
            "payment_history": 15,
            "product_adoption": 0,
        },
        ScoreTier.D.value,
        0,
    ),
    (
        {
            "engagement_level": 60,
            "deal_velocity": 55,
            "support_health": 50,
            "payment_history": 45,
            "product_adoption": 50,
        },
        (ScoreTier.B.value, ScoreTier.C.value),
        40,
    ),
    (
        None,
        ScoreTier.C.value,
        50,
    ),
]


@pytest.fixture
def tier_service(request):
    score_factors, expected_tier, score_bound = TIER_CASES[request.param]
    state = MockState()
    _seed_customer(state, score_factors)
    svc = ScoreService(_make_session(state))
    return svc, expected_tier, score_bound


@pytest.mark.parametrize("tier_service", list(range(len(TIER_CASES))), indirect=True)
@pytest.mark.asyncio
async def test_calculate_score_tier(tier_service):
    svc, expected_tier, score_bound = tier_service
    score, tier, factors, recs, similar_leads = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    if isinstance(expected_tier, tuple):
        assert tier in expected_tier
    else:
        assert tier == expected_tier
    if score_bound >= 40:
        assert score >= score_bound
    else:
        assert score < 40
    assert len(factors) <= 3
    assert len(recs) <= 3
    assert len(factors) == len(recs)


@pytest.mark.asyncio
async def test_calculate_score_not_found():
    state = MockState()
    svc = ScoreService(_make_session(state))
    with pytest.raises(NotFoundException):
        await svc.calculate_score(999, TENANT_ID)


@pytest.mark.asyncio
async def test_calculate_score_cross_tenant_raises_not_found():
    """A customer owned by a different tenant must not be visible."""
    state = MockState()
    state.customers[CUSTOMER_ID] = {
        "id": CUSTOMER_ID,
        "tenant_id": OTHER_TENANT_ID,
        "score_factors": {"engagement_level": 90},
    }
    svc = ScoreService(_make_session(state))
    with pytest.raises(NotFoundException):
        await svc.calculate_score(CUSTOMER_ID, TENANT_ID)


@pytest.mark.asyncio
async def test_get_score_delegates(score_service):
    r1 = await score_service.get_score(CUSTOMER_ID, TENANT_ID)
    r2 = await score_service.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert r1 == r2


@pytest.mark.asyncio
async def test_top_factors_excludes_zero():
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 80,
            "deal_velocity": 0,
            "support_health": 70,
            "payment_history": 0,
            "product_adoption": 90,
        },
    )
    svc = ScoreService(_make_session(state))
    _, _, factors, _, _ = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert "deal_velocity" not in factors
    assert "payment_history" not in factors
    assert all(f not in ("deal_velocity", "payment_history") for f in factors)


@pytest.mark.asyncio
async def test_recommendations_match_top_factors():
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 80,
            "deal_velocity": 75,
            "support_health": 70,
            "payment_history": 65,
            "product_adoption": 60,
        },
    )
    svc = ScoreService(_make_session(state))
    _, _, factors, recs, _ = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert len(factors) == len(recs)
    for f, r in zip(factors, recs, strict=True):
        assert r == FIELD_RECOMMENDATIONS[f]


# ---------------------------------------------------------------------------
# AI agent branch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_score_ai_branch():
    """When AIAgentClient returns data, similar_leads and recommendations are enriched."""
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 80,
            "deal_velocity": 75,
            "support_health": 70,
            "payment_history": 65,
            "product_adoption": 60,
        },
    )
    svc = ScoreService(_make_session(state))

    mock_agent_instance = AsyncMock()
    mock_agent_instance.analyze_factors = AsyncMock(
        return_value={
            "similar_leads": [{"id": 42, "score": 0.9}],
            "recommendations": ["Expand to segment B"],
        }
    )
    mock_agent_class = MagicMock(return_value=mock_agent_instance)

    with patch("services.score_service.AIAgentClient", mock_agent_class):
        score, tier, factors, recs, similar_leads = await svc.calculate_score(
            CUSTOMER_ID, TENANT_ID, include_ai=True
        )

    assert similar_leads == [{"id": 42, "score": 0.9}]
    assert recs == ["Expand to segment B"]
    assert isinstance(score, int)
    assert tier in ("A", "B", "C", "D")
    assert factors
    mock_agent_class.assert_called_once()
    mock_agent_instance.analyze_factors.assert_awaited_once_with(
        entity_id=CUSTOMER_ID,
        tenant_id=TENANT_ID,
        current_score=score,
    )


@pytest.mark.asyncio
async def test_calculate_score_ai_fallback():
    """When AIAgentClient raises, scoring degrades gracefully (similar_leads == [])."""
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 80,
            "deal_velocity": 75,
            "support_health": 70,
            "payment_history": 65,
            "product_adoption": 60,
        },
    )
    svc = ScoreService(_make_session(state))

    mock_agent_instance = AsyncMock()
    mock_agent_instance.analyze_factors = AsyncMock(side_effect=Exception("agent down"))
    mock_agent_class = MagicMock(return_value=mock_agent_instance)

    with patch("services.score_service.AIAgentClient", mock_agent_class):
        score, tier, factors, recs, similar_leads = await svc.calculate_score(
            CUSTOMER_ID, TENANT_ID, include_ai=True
        )

    assert similar_leads == []
    assert isinstance(score, int)
    assert score > 0
    assert tier in ("A", "B", "C", "D")
    assert factors
    assert recs
    mock_agent_class.assert_called_once()


@pytest.mark.asyncio
async def test_calculate_score_include_ai_false_skips_agent():
    """When include_ai=False, the AI client is never instantiated."""
    state = MockState()
    _seed_customer(
        state,
        {
            "engagement_level": 80,
            "deal_velocity": 75,
            "support_health": 70,
            "payment_history": 65,
            "product_adoption": 60,
        },
    )
    svc = ScoreService(_make_session(state))

    mock_agent_class = MagicMock(return_value=AsyncMock())

    with patch("services.score_service.AIAgentClient", mock_agent_class):
        score, tier, factors, recs, similar_leads = await svc.calculate_score(
            CUSTOMER_ID, TENANT_ID, include_ai=False
        )

    assert similar_leads == []
    assert isinstance(score, int)
    assert tier in ("A", "B", "C", "D")
    assert factors
    assert recs
    mock_agent_class.assert_not_called()
