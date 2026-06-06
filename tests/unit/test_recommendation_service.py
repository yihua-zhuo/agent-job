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
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    _cache.clear()
    return RecommendationService(mock_db_session)


async def test_cache_miss_populates_cache(svc):
    result = await svc.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    assert key in _cache
    ts, cached_data = _cache[key]
    assert ts == 1000.0
    assert cached_data == result


async def test_cache_hit_returns_cached_data(svc):
    result1 = await svc.get_recommendations(1, tenant_id=1)
    result2 = await svc.get_recommendations(1, tenant_id=1)
    assert result1 == result2


async def test_stale_cache_is_bypassed(svc, monkeypatch):
    await svc.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    ts_before, _ = _cache[key]
    monkeypatch.setattr(time, "time", lambda: 1000.0 + _CACHE_TTL + 1)
    await svc.get_recommendations(1, tenant_id=1)
    ts_after, _ = _cache[key]
    assert ts_after > ts_before


async def test_invalidate_removes_cache_entry(svc):
    await svc.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    assert key in _cache
    RecommendationService.invalidate_cache(1, 1)
    assert key not in _cache


async def test_invalidate_on_missing_key_does_not_raise():
    RecommendationService.invalidate_cache(999, 999)


async def test_not_found_raises(svc, mock_db_session):
    class _EmptyResult:
        def scalar_one_or_none(self):
            return None

    mock_db_session.execute = AsyncMock(return_value=_EmptyResult())
    with pytest.raises(NotFoundException):
        await svc.get_recommendations(9999, tenant_id=1)


async def test_tenant_isolation_in_cache_key(svc):
    await svc.get_recommendations(1, tenant_id=1)
    await svc.get_recommendations(1, tenant_id=2)
    assert _cache_key(1, 1) in _cache
    assert _cache_key(1, 2) in _cache
    assert _cache_key(1, 1) != _cache_key(1, 2)
