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

import importlib
import importlib.util
import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from models.score import ScoreTier, SimilarLead
from pkg.errors.app_exceptions import NotFoundException

logger = logging.getLogger(__name__)

# Lazy lookup for the TBD AI client. We use importlib.util.find_spec so that
# SyntaxError or other non-ImportError issues in the TBD module do not
# propagate through the import-time fallback.
AIAgentClient: type | None = None
if importlib.util.find_spec("services.ai_agent_client") is not None:
    _ai_module = importlib.import_module("services.ai_agent_client")
    AIAgentClient = getattr(_ai_module, "AIAgentClient", None)


class _AIAgentClientProtocol(Protocol):
    """Structural type for an injected AI client. The real ``AIAgentClient``
    (when implemented) is expected to satisfy this protocol."""

    async def analyze_factors(
        self,
        *,
        entity_id: int,
        tenant_id: int,
        current_score: int,
    ) -> dict: ...


DEFAULT_SCORE = 50
DEFAULT_TIER = ScoreTier.C

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


@dataclass
class ScoreResult:
    """Typed result returned by calculate_score / get_score.

    Using a dataclass instead of a positional tuple keeps callers
    resilient to field reordering and self-documenting at call sites.
    """

    score: int
    tier: ScoreTier
    top_factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    similar_leads: list[SimilarLead] = field(default_factory=list)

    @property
    def tier_label(self) -> str:
        """Return the string form of the tier (decouples callers from the enum)."""
        return self.tier.value


class ScoreService:
    def __init__(self, session: AsyncSession, ai_client: _AIAgentClientProtocol | None = None):
        self.session = session
        self._ai_client = ai_client

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
        client = self._ai_client
        if client is None:
            return {}
        try:
            result = await client.analyze_factors(
                entity_id=customer_id,
                tenant_id=tenant_id,
                current_score=current_score,
            )
        except (TimeoutError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("AI agent call failed for customer %s: %s", customer_id, exc)
            return {}

        if not isinstance(result, dict):
            return {}

        similar_leads_raw = result.get("similar_leads") or []
        recommendations = result.get("recommendations") or []
        if not isinstance(similar_leads_raw, list):
            similar_leads_raw = []
        if not isinstance(recommendations, list):
            recommendations = []

        parsed: list[SimilarLead] = []
        for item in similar_leads_raw[:MAX_SIMILAR_LEADS]:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if not isinstance(raw_id, int) or raw_id <= 0:
                continue
            try:
                parsed.append(
                    SimilarLead(
                        id=raw_id,
                        score=float(item.get("score", 0.0)),
                        name=item.get("name"),
                    )
                )
            except (TypeError, ValueError):
                continue

        return {
            "similar_leads": parsed,
            "recommendations": recommendations,
        }

    async def calculate_score(
        self,
        customer_id: int,
        tenant_id: int,
        include_ai: bool = True,
    ) -> ScoreResult:
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
        similar_leads: list[SimilarLead] = []
        top_factors: list[str] = []
        recommendations: list[str] = []
        tier: ScoreTier
        score: int

        if not score_factors:
            score = DEFAULT_SCORE
            tier = DEFAULT_TIER
        else:
            total = 0
            contributions: dict[str, int] = {}
            for field_name, weight in FIELD_WEIGHTS.items():
                factor_score = int(score_factors.get(field_name, 0))
                factor_score = max(0, min(100, factor_score))
                contributions[field_name] = factor_score
                # Integer-division: weights are percentages that sum to 100,
                # so floor division gives an exact integer total.
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
                # AI recommendations are authoritative when present;
                # static FIELD_RECOMMENDATIONS are the fallback when AI is
                # absent or returns nothing. Merge: AI first, static fills gaps.
                static_keys = [f for f in top_factors if f in FIELD_RECOMMENDATIONS]
                static_recs = [FIELD_RECOMMENDATIONS[f] for f in static_keys]
                merged = list(ai_recs)
                for rec in static_recs:
                    if rec not in merged:
                        merged.append(rec)
                recommendations = merged

        return ScoreResult(
            score=score,
            tier=tier,
            top_factors=top_factors,
            recommendations=recommendations,
            similar_leads=similar_leads,
        )

    async def get_score(
        self,
        customer_id: int,
        tenant_id: int,
        include_ai: bool = True,
    ) -> ScoreResult:
        score_result = await self.calculate_score(customer_id, tenant_id, include_ai=include_ai)
        # Treat the customer as "never scored" only if the persisted factor
        # data is absent. top_factors/recommendations are derived views and can
        # legitimately be empty (e.g. all factor scores == 0).
        result = await self.session.execute(
            select(CustomerModel).where(
                CustomerModel.id == customer_id,
                CustomerModel.tenant_id == tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None or not customer.score_factors:
            raise NotFoundException("Score")
        return score_result
