"""ScoreService — static, non-AI health score for customers.

Reads the persisted ``score_factors`` JSON column on ``CustomerModel`` (populated by the
upstream scoring pipeline), sums each factor's contribution, clamps to 0–100, classifies
into a tier (A/B/C/D), surfaces the top contributing factors, and returns actionable
recommendations. No AI / LLM calls are made in this module.

When ``include_ai`` is ``True`` (default), ``calculate_score`` also calls
``AIAgentClient.analyze_factors`` to enrich the result with ``similar_leads`` and
AI-generated recommendations. The AI call is wrapped in a try/except so that
agent unavailability or malformed payloads degrade gracefully to a static score
with an empty ``similar_leads`` list — the static score is never lost.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from models.score import ScoreTier
from pkg.errors.app_exceptions import NotFoundException

try:
    from services.ai_agent_client import AIAgentClient  # type: ignore[import-not-found]
except ImportError:
    AIAgentClient = None  # type: ignore[assignment,misc]

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
MAX_SIMILAR_LEADS = 10


class ScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ai_annotate_score(
        self,
        customer_id: int,
        tenant_id: int,
        current_score: int,
    ) -> dict:
        """Call the AI Agent Framework for deeper factor analysis.

        Returns a dict with ``similar_leads`` and ``recommendations`` keys, or an
        empty dict on any failure (timeout, non-200, malformed payload, missing
        client). ``similar_leads`` is capped at ``MAX_SIMILAR_LEADS`` items.
        """
        if AIAgentClient is None:
            return {}
        try:
            agent = AIAgentClient()
            result = await agent.analyze_factors(
                entity_id=customer_id,
                tenant_id=tenant_id,
                current_score=current_score,
            )
        except Exception:
            return {}

        if not isinstance(result, dict):
            return {}

        similar_leads = result.get("similar_leads") or []
        recommendations = result.get("recommendations") or []
        if not isinstance(similar_leads, list):
            similar_leads = []
        if not isinstance(recommendations, list):
            recommendations = []

        return {
            "similar_leads": similar_leads[:MAX_SIMILAR_LEADS],
            "recommendations": recommendations,
        }

    async def calculate_score(
        self,
        customer_id: int,
        tenant_id: int,
        include_ai: bool = True,
    ) -> tuple[int, str, list[str], list[str], list[dict]]:
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
        similar_leads: list[dict] = []
        top_factors: list[str] = []
        recommendations: list[str] = []

        if not score_factors:
            score, tier = 50, ScoreTier.C.value
        else:
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

        if include_ai:
            ai_data = await self.ai_annotate_score(customer_id, tenant_id, score)
            ai_similar = ai_data.get("similar_leads") or []
            if ai_similar:
                similar_leads = ai_similar
            ai_recs = ai_data.get("recommendations") or []
            if ai_recs:
                recommendations = ai_recs

        return score, tier, top_factors, recommendations, similar_leads

    async def get_score(
        self,
        customer_id: int,
        tenant_id: int,
        include_ai: bool = True,
    ) -> tuple[int, str, list[str], list[str], list[dict]]:
        result = await self.calculate_score(customer_id, tenant_id, include_ai=include_ai)
        score, _tier, top_factors, recommendations, _similar_leads = result
        if not top_factors and not recommendations:
            raise NotFoundException("Score")
        return result
