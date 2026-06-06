"""Recommendation service with in-memory TTL caching.

Wraps SalesRecommendationService and caches per-(opportunity_id, tenant_id)
results in a module-level dict for 3600s.
"""

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException
from services.sales_recommendation import SalesRecommendationService

_CACHE_TTL = 3600.0  # seconds

# Module-level singleton cache — survives across service instances within a process.
_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(opportunity_id: int, tenant_id: int) -> str:
    return f"{opportunity_id}:{tenant_id}"


class RecommendationService:
    __slots__ = ("session", "_sales_svc")

    def __init__(self, session: AsyncSession):
        self.session = session
        self._sales_svc = SalesRecommendationService()

    async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:
        key = _cache_key(opportunity_id, tenant_id)
        now = time.time()
        if key in _cache:
            ts, data = _cache[key]
            if now - ts < _CACHE_TTL:
                return data
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opportunity_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        opp = result.scalar_one_or_none()
        if opp is None:
            raise NotFoundException("Opportunity")
        data = {
            "opportunity_id": opportunity_id,
            "conversion_probability": self._sales_svc.predict_conversion_probability(opportunity_id),
            "next_action": self._sales_svc.get_next_best_action(tenant_id, opp.customer_id),
            "similar_deals": [],
        }
        _cache[key] = (now, data)
        return data

    @staticmethod
    def invalidate_cache(opportunity_id: int, tenant_id: int) -> None:
        _cache.pop(_cache_key(opportunity_id, tenant_id), None)
