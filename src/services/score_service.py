"""ScoreService — static, non-AI health score for customers.

Reads the persisted ``score_factors`` JSON column on ``CustomerModel`` (populated by the
upstream scoring pipeline), sums each factor's contribution, clamps to 0–100, classifies
into a tier (A/B/C/D), surfaces the top contributing factors, and returns actionable
recommendations. No AI / LLM calls are made in this module.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from models.score import ScoreTier
from pkg.errors.app_exceptions import NotFoundException

FIELD_WEIGHTS: dict[str, int] = {
    "engagement_level": 30,
    "deal_velocity": 25,
    "support_health": 20,
    "payment_history": 15,
    "product_adoption": 10,
}

TIER_BOUNDARIES: list[tuple[int, ScoreTier]] = [
    (80, ScoreTier.A),
    (60, ScoreTier.B),
    (40, ScoreTier.C),
]

FIELD_RECOMMENDATIONS: dict[str, str] = {
    "engagement_level": "Increase touchpoints with targeted campaigns",
    "deal_velocity": "Accelerate pipeline with limited-time offers",
    "support_health": "Resolve open tickets and schedule a QBR",
    "payment_history": "Review billing terms and clear outstanding invoices",
    "product_adoption": "Provide onboarding session for underused features",
}

MAX_TOP_FACTORS = 3


class ScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_score(self, customer_id: int, tenant_id: int) -> tuple[int, str, list[str], list[str]]:
        result = await self.session.execute(
            select(CustomerModel).where(
                CustomerModel.id == customer_id,
                CustomerModel.tenant_id == tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")

        score_factors = customer.score_factors
        if not score_factors:
            return 50, ScoreTier.C.value, [], []

        total = 0
        contributions: dict[str, int] = {}
        for field_name, weight in FIELD_WEIGHTS.items():
            factor_score = int(score_factors.get(field_name, 0))
            factor_score = max(0, min(100, factor_score))
            contributions[field_name] = factor_score
            total += factor_score * weight // 100

        score = max(0, min(100, total))

        tier = ScoreTier.D
        for threshold, t in TIER_BOUNDARIES:
            if score >= threshold:
                tier = t
                break

        sorted_contrib = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
        top_factors = [k for k, v in sorted_contrib[:MAX_TOP_FACTORS] if v > 0]
        recommendations = [FIELD_RECOMMENDATIONS[f] for f in top_factors if f in FIELD_RECOMMENDATIONS]

        return score, tier.value, top_factors, recommendations

    async def get_score(self, customer_id: int, tenant_id: int) -> tuple[int, str, list[str], list[str]]:
        return await self.calculate_score(customer_id, tenant_id)
