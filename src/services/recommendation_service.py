"""Recommendation service with bounded in-memory TTL caching.

Wraps SalesRecommendationService and caches per-(opportunity_id, tenant_id)
results in an LRU+TTL dict for up to 3600s. Uses ``time.monotonic()`` for TTL
comparison so wall-clock changes (NTP, DST) cannot extend a cache entry's
lifetime beyond the configured window.
"""

import time
from collections import OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException
from services.sales_recommendation import SalesActionRecommendation, SalesRecommendationService

_CACHE_TTL = 3600.0  # seconds
_CACHE_MAX_ENTRIES = 1024


class _TLRUCache:
    """Time-aware LRU cache — evicts least-recently-used entries past the TTL
    or when the entry-count cap is exceeded.
    """

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def get(self, key: str) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts < _CACHE_TTL:
            self._entries.move_to_end(key)
            return value
        del self._entries[key]
        return None

    def peek(self, key: str) -> object | None:
        """Return the cached value without updating recency. Test-only helper."""
        entry = self._entries.get(key)
        return None if entry is None else entry[1]

    def timestamp(self, key: str) -> float:
        """Return the insertion timestamp for a key. Test-only helper."""
        entry = self._entries[key]
        return entry[0]

    def set(self, key: str, value: object) -> None:
        if key in self._entries:
            self._entries.move_to_end(key)
        self._entries[key] = (time.monotonic(), value)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def pop(self, key: str) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._entries


_cache = _TLRUCache(max_entries=_CACHE_MAX_ENTRIES)


def _cache_key(opportunity_id: int, tenant_id: int) -> str:
    return f"{opportunity_id}:{tenant_id}"


@dataclass
class CachedRecommendationResult:
    """Cached recommendation result returned by RecommendationService.get_recommendations."""

    opportunity_id: int
    conversion_probability: float
    next_best_action: SalesActionRecommendation
    similar_opportunities: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "conversion_probability": self.conversion_probability,
            "next_best_action": self.next_best_action.to_dict(),
            "similar_opportunities": self.similar_opportunities,
        }


class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._sales_svc = SalesRecommendationService(session)

    async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> CachedRecommendationResult:
        key = _cache_key(opportunity_id, tenant_id)
        cached = _cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opportunity_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        opp = result.scalar_one_or_none()
        if opp is None:
            raise NotFoundException("Opportunity")
        similar = self._sales_svc.get_similar_customers(tenant_id, opp.customer_id)
        data = CachedRecommendationResult(
            opportunity_id=opportunity_id,
            conversion_probability=self._sales_svc.predict_conversion_probability(opportunity_id, tenant_id),
            next_best_action=self._sales_svc.get_next_best_action(tenant_id, opp.customer_id),
            similar_opportunities=[
                {
                    "customer_id": s.customer_id,
                    "current_tier": s.current_tier,
                    "monthly_revenue": s.monthly_revenue,
                }
                for s in similar
            ],
        )
        _cache.set(key, data)
        return data

    @staticmethod
    def invalidate_cache(opportunity_id: int, tenant_id: int) -> None:
        _cache.pop(_cache_key(opportunity_id, tenant_id))
