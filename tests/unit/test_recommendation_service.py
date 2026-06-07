"""Unit tests for src/services/recommendation_service.py."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.recommendation_service import (
    _CACHE_TTL,
    RecommendationService,
    _cache,
    _cache_key,
)
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.customers import make_customer_handler
from tests.unit.domain_handlers.sales import opportunity_handler


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([opportunity_handler, make_customer_handler(state)])


@pytest.fixture
def svc(mock_db_session, monkeypatch):
    # Use a controllable clock for both the production code (monotonic) and
    # the test's read of cached timestamps.
    clock = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
    _cache.clear()
    return RecommendationService(mock_db_session), clock


async def test_cache_miss_populates_cache(svc):
    service, clock = svc
    result = await service.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    assert key in _cache
    cached_data = _cache.peek(key)
    assert cached_data == result
    assert clock["t"] == 1000.0


async def test_cache_hit_returns_cached_data(svc):
    service, _ = svc
    result1 = await service.get_recommendations(1, tenant_id=1)
    result2 = await service.get_recommendations(1, tenant_id=1)
    assert result1 == result2


async def test_stale_cache_is_bypassed(svc, monkeypatch):
    service, clock = svc
    await service.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    first_ts = _cache.timestamp(key)
    clock["t"] += _CACHE_TTL + 1
    await service.get_recommendations(1, tenant_id=1)
    second_ts = _cache.timestamp(key)
    assert second_ts > first_ts


async def test_invalidate_removes_cache_entry(svc):
    service, _ = svc
    await service.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    assert key in _cache
    RecommendationService.invalidate_cache(1, 1)
    assert key not in _cache


async def test_invalidate_on_missing_key_does_not_raise():
    RecommendationService.invalidate_cache(999, 999)


async def test_not_found_raises(svc, mock_db_session):
    service, _ = svc

    class _EmptyResult:
        def scalar_one_or_none(self):
            return None

    mock_db_session.execute = AsyncMock(return_value=_EmptyResult())
    with pytest.raises(NotFoundException):
        await service.get_recommendations(9999, tenant_id=1)


async def test_tenant_isolation_in_cache_key(svc):
    service, _ = svc
    await service.get_recommendations(1, tenant_id=1)
    await service.get_recommendations(1, tenant_id=2)
    assert _cache_key(1, 1) in _cache
    assert _cache_key(1, 2) in _cache
    assert _cache_key(1, 1) != _cache_key(1, 2)
