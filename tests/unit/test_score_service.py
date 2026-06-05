"""Unit tests for ScoreService."""

from __future__ import annotations

import pytest

from models.score import ScoreTier
from pkg.errors.app_exceptions import NotFoundException
from services.score_service import FIELD_RECOMMENDATIONS, ScoreService
from tests.unit.conftest import MockResult, MockRow, MockState, make_mock_session

CUSTOMER_ID = 1
TENANT_ID = 10


def _make_session(customer: dict | None) -> object:
    state = MockState()
    if customer is not None:
        state.customers[CUSTOMER_ID] = customer
        rows = [MockRow(customer)]
    else:
        rows = []

    def handler(sql_text, params):
        if "from customers" in sql_text and "where" in sql_text:
            return MockResult(rows=rows)
        return None

    return make_mock_session(handlers=[handler], state=state)


@pytest.fixture
def score_service():
    return ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 90,
            "deal_velocity": 85,
            "support_health": 80,
            "payment_history": 75,
            "product_adoption": 70,
        },
    }))


@pytest.mark.asyncio
async def test_calculate_score_tier_a(score_service):
    score, tier, factors, recs = await score_service.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert score >= 80
    assert tier == ScoreTier.A.value
    assert len(factors) <= 3
    assert len(recs) <= 3
    assert len(factors) == len(recs)


@pytest.mark.asyncio
async def test_calculate_score_tier_d():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 5,
            "deal_velocity": 10,
            "support_health": 0,
            "payment_history": 15,
            "product_adoption": 0,
        },
    }))
    score, tier, factors, recs = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert score < 40
    assert tier == ScoreTier.D.value
    assert len(factors) <= 3


@pytest.mark.asyncio
async def test_calculate_score_tier_b_or_c():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 60,
            "deal_velocity": 55,
            "support_health": 50,
            "payment_history": 45,
            "product_adoption": 50,
        },
    }))
    score, tier, factors, recs = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert 40 <= score < 80
    assert tier in (ScoreTier.B.value, ScoreTier.C.value)
    assert len(factors) <= 3
    assert len(factors) == len(recs)


@pytest.mark.asyncio
async def test_calculate_score_not_found():
    svc = ScoreService(_make_session(None))
    with pytest.raises(NotFoundException):
        await svc.calculate_score(999, TENANT_ID)


@pytest.mark.asyncio
async def test_calculate_score_none_factors():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": None,
    }))
    score, tier, factors, recs = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert score == 50
    assert tier == ScoreTier.C.value
    assert factors == []
    assert recs == []


@pytest.mark.asyncio
async def test_get_score_delegates():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 70,
            "deal_velocity": 65,
            "support_health": 60,
            "payment_history": 55,
            "product_adoption": 50,
        },
    }))
    r1 = await svc.get_score(CUSTOMER_ID, TENANT_ID)
    r2 = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert r1 == r2


@pytest.mark.asyncio
async def test_top_factors_excludes_zero():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 80,
            "deal_velocity": 0,
            "support_health": 70,
            "payment_history": 0,
            "product_adoption": 90,
        },
    }))
    _, _, factors, _ = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert "deal_velocity" not in factors
    assert "payment_history" not in factors
    assert all(f not in ("deal_velocity", "payment_history") for f in factors)


@pytest.mark.asyncio
async def test_recommendations_match_top_factors():
    svc = ScoreService(_make_session({
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": {
            "engagement_level": 80,
            "deal_velocity": 75,
            "support_health": 70,
            "payment_history": 65,
            "product_adoption": 60,
        },
    }))
    _, _, factors, recs = await svc.calculate_score(CUSTOMER_ID, TENANT_ID)
    assert len(factors) == len(recs)
    for f, r in zip(factors, recs, strict=False):
        assert r == FIELD_RECOMMENDATIONS[f]
