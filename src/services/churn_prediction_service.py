"""ChurnPredictionService — rule-based real-time churn scoring (0-100).

Computes a weighted churn score from four customer dimensions and returns
a ``ChurnPrediction`` dataclass. No DB writes — all queries are read-only.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from db.models.ticket import TicketModel
from pkg.errors.app_exceptions import NotFoundException


@dataclass
class ChurnRiskFactor:
    """Single churn risk dimension contributing to the overall score."""

    name: str
    weight: float
    score: float
    description: str


@dataclass
class ChurnPrediction:
    """Result of a real-time churn scoring calculation."""

    customer_id: int
    score: float
    tier: str
    top_3_risk_factors: list[ChurnRiskFactor] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)


class ChurnPredictionService:
    """Rule-based churn scoring — 4-dimension weighted engine, no DB writes."""

    WEIGHTS: dict[str, float] = {
        "login_frequency": 0.25,
        "purchase_recency": 0.25,
        "support_ticket_count": 0.25,
        "engagement_score": 0.25,
    }

    _FACTOR_DESCRIPTIONS: dict[str, str] = {
        "login_frequency": "login frequency in the last 30 days",
        "purchase_recency": "days since the last won opportunity",
        "support_ticket_count": "open/pending support ticket burden",
        "engagement_score": "overall activity-based engagement",
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch_raw_metrics(self, customer_id: int, tenant_id: int) -> dict:
        """Read raw per-dimension counts/dates for a single customer."""
        result = await self.session.execute(
            select(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")

        now = datetime.now(UTC)
        login_window = now - timedelta(days=30)

        login_result = await self.session.execute(
            select(func.count(ActivityModel.id)).where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                    ActivityModel.created_at >= login_window,
                )
            )
        )
        login_frequency = int(login_result.scalar() or 0)

        purchase_result = await self.session.execute(
            select(func.max(OpportunityModel.created_at)).where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id == customer_id,
                    OpportunityModel.stage == "won",
                )
            )
        )
        last_purchase = purchase_result.scalar()
        if last_purchase is not None:
            if last_purchase.tzinfo is None:
                last_purchase = last_purchase.replace(tzinfo=UTC)
            purchase_recency_days = max(0, (now - last_purchase).days)
        else:
            purchase_recency_days = 90

        ticket_result = await self.session.execute(
            select(func.count(TicketModel.id)).where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.customer_id == customer_id,
                    TicketModel.status.in_(("open", "pending")),
                )
            )
        )
        support_ticket_count = int(ticket_result.scalar() or 0)

        return {
            "login_frequency": login_frequency,
            "purchase_recency_days": purchase_recency_days,
            "support_ticket_count": support_ticket_count,
            "engagement_score_raw": login_frequency,
        }

    @staticmethod
    def _normalize_score(name: str, raw: float) -> float:
        """Map a raw dimension value to a 0-100 sub-score.

        Higher sub-score = healthier / lower churn risk for that dimension.
        Support tickets and purchase recency are inverted: more tickets or
        more days = lower health.
        """
        if name == "login_frequency":
            return min(raw / 10 * 100, 100)
        if name == "purchase_recency":
            return max(0.0, 100.0 - raw)
        if name == "support_ticket_count":
            return min(raw / 5 * 100, 100)
        if name == "engagement_score":
            return min(raw / 30 * 100, 100)
        return 0.0

    @staticmethod
    def _compute_tier(score: float) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _build_top_3_factors(self, name_to_score: dict[str, float]) -> list[ChurnRiskFactor]:
        """Return the three dimensions with the highest sub-scores (healthiest first)."""
        ranked = sorted(name_to_score.items(), key=lambda item: item[1], reverse=True)
        top_3 = ranked[:3]
        return [
            ChurnRiskFactor(
                name=name,
                weight=self.WEIGHTS[name],
                score=score,
                description=self._FACTOR_DESCRIPTIONS.get(name, name),
            )
            for name, score in top_3
        ]

    async def calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction:
        """Compute churn score, tier, top factors, and recommended actions."""
        raw = await self._fetch_raw_metrics(customer_id, tenant_id)

        login_score = self._normalize_score("login_frequency", raw["login_frequency"])
        purchase_score = self._normalize_score("purchase_recency", raw["purchase_recency_days"])
        support_score = self._normalize_score("support_ticket_count", raw["support_ticket_count"])
        engagement_score = self._normalize_score("engagement_score", raw["engagement_score_raw"])

        raw_total = login_score * 0.25 + purchase_score * 0.25 + (100 - support_score) * 0.25 + engagement_score * 0.25
        score = round(min(raw_total, 100.0), 2)

        name_to_score = {
            "login_frequency": login_score,
            "purchase_recency": purchase_score,
            "support_ticket_count": support_score,
            "engagement_score": engagement_score,
        }
        top_3_risk_factors = self._build_top_3_factors(name_to_score)

        recommended_actions: list[str] = []
        if raw["support_ticket_count"] > 2:
            recommended_actions.append("优先处理客户工单，降低流失风险")
        if raw["purchase_recency_days"] > 60:
            recommended_actions.append("客户长期无购买记录，触发重新激活营销")
        if raw["login_frequency"] < 3:
            recommended_actions.append("客户登录频率低，建议发送个性化内容激活")
        if not recommended_actions:
            recommended_actions.append("客户状态健康，维持常规维护")

        return ChurnPrediction(
            customer_id=customer_id,
            score=score,
            tier=self._compute_tier(score),
            top_3_risk_factors=top_3_risk_factors,
            recommended_actions=recommended_actions,
        )
