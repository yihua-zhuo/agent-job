"""ChurnPredictionService — rule-based real-time churn scoring (0-100).

Computes a weighted churn score from four customer dimensions and returns
a ``ChurnPrediction`` dataclass. No DB writes (read-only queries against
activity, opportunity, and ticket tables).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.churn_prediction import ChurnPredictionModel
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

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "description": self.description,
        }


@dataclass
class ChurnPrediction:
    """Result of a real-time churn scoring calculation."""

    customer_id: int
    score: float
    tier: str
    top_3_risk_factors: list[ChurnRiskFactor] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "score": self.score,
            "tier": self.tier,
            "top_3_risk_factors": [f.to_dict() for f in self.top_3_risk_factors],
            "recommended_actions": list(self.recommended_actions),
        }


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
        "engagement_score": "diversity of activity types in the last 30 days",
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
        engagement_result = await self.session.execute(
            select(func.count(func.distinct(ActivityModel.type))).where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                    ActivityModel.created_at >= login_window,
                )
            )
        )
        purchase_result = await self.session.execute(
            select(func.max(OpportunityModel.created_at)).where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id == customer_id,
                    OpportunityModel.stage == "won",
                )
            )
        )
        ticket_result = await self.session.execute(
            select(func.count(TicketModel.id)).where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.customer_id == customer_id,
                    TicketModel.status.in_(("open", "pending")),
                )
            )
        )

        login_frequency = int(login_result.scalar() or 0)
        engagement_diversity = int(engagement_result.scalar() or 0)

        last_purchase = purchase_result.scalar()
        if last_purchase is not None:
            if last_purchase.tzinfo is None:
                last_purchase = last_purchase.replace(tzinfo=UTC)
            purchase_recency_days = max(0.0, (now - last_purchase).total_seconds() / 86400.0)
        else:
            purchase_recency_days = 90

        support_ticket_count = int(ticket_result.scalar() or 0)

        return {
            "login_frequency": login_frequency,
            "purchase_recency_days": purchase_recency_days,
            "support_ticket_count": support_ticket_count,
            "engagement_score_raw": engagement_diversity,
        }

    @staticmethod
    def _normalize_score(name: str, raw: float) -> float:
        """Map a raw dimension value to a 0-100 health sub-score.

        Higher sub-score = healthier / lower churn risk for that dimension.
        Each branch returns a true health score, so the caller can sum them
        directly without double-inverting.
        """
        if name == "login_frequency":
            return min(raw / 10 * 100, 100)
        if name == "purchase_recency":
            return max(0.0, 100.0 - raw)
        if name == "support_ticket_count":
            return max(0.0, 100.0 - min(raw / 5 * 100, 100))
        if name == "engagement_score":
            return min(raw / 5 * 100, 100)
        return 0.0

    @staticmethod
    def _compute_tier(score: float) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _build_top_3_factors(self, name_to_score: dict[str, float]) -> list[ChurnRiskFactor]:
        """Return the three dimensions with the highest churn risk (lowest health first)."""
        name_to_risk = {name: 100.0 - score for name, score in name_to_score.items()}
        ranked = sorted(name_to_risk.items(), key=lambda item: item[1], reverse=True)
        top_3 = ranked[:3]
        return [
            ChurnRiskFactor(
                name=name,
                weight=self.WEIGHTS[name],
                score=name_to_score[name],
                description=self._FACTOR_DESCRIPTIONS.get(name, name),
            )
            for name, _ in top_3
        ]

    async def calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction:
        """Compute churn score, tier, top factors, and recommended actions."""
        raw = await self._fetch_raw_metrics(customer_id, tenant_id)

        name_to_score = {
            "login_frequency": self._normalize_score("login_frequency", raw["login_frequency"]),
            "purchase_recency": self._normalize_score("purchase_recency", raw["purchase_recency_days"]),
            "support_ticket_count": self._normalize_score("support_ticket_count", raw["support_ticket_count"]),
            "engagement_score": self._normalize_score("engagement_score", raw["engagement_score_raw"]),
        }
        raw_total = sum(score * self.WEIGHTS[name] for name, score in name_to_score.items())
        score = round(max(0.0, min(raw_total, 100.0)), 2)

        top_3_risk_factors = self._build_top_3_factors(name_to_score)

        return ChurnPrediction(
            customer_id=customer_id,
            score=score,
            tier=self._compute_tier(score),
            top_3_risk_factors=top_3_risk_factors,
            recommended_actions=self._build_recommended_actions(raw),
        )

    async def get_or_compute_prediction(self, customer_id: int, tenant_id: int) -> ChurnPrediction:
        """Return the latest stored prediction, or compute a fresh one if none exists.

        Raises NotFoundException if the customer itself does not exist.
        """
        try:
            return await self.get_churn_prediction(customer_id, tenant_id=tenant_id)
        except NotFoundException:
            return await self.calculate_score(customer_id, tenant_id=tenant_id)

    async def get_churn_prediction(self, customer_id: int, tenant_id: int) -> ChurnPrediction:
        """Return the latest stored churn prediction for a customer, or raise NotFoundException."""
        result = await self.session.execute(
            select(ChurnPredictionModel)
            .where(
                and_(
                    ChurnPredictionModel.tenant_id == tenant_id,
                    ChurnPredictionModel.customer_id == customer_id,
                )
            )
            .order_by(ChurnPredictionModel.predicted_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("ChurnPrediction")

        factors = [
            ChurnRiskFactor(
                name=f.get("name", ""),
                weight=float(f.get("weight", 0.0)),
                score=float(f.get("score", 0.0)),
                description=f.get("description", ""),
            )
            for f in (row.factors or [])
        ]
        actions = [
            str(a.get("action", "")) if isinstance(a, dict) else str(a)
            for a in (row.recommended_actions or [])
        ]
        tier_value = row.tier.value if hasattr(row.tier, "value") else str(row.tier)
        return ChurnPrediction(
            customer_id=row.customer_id,
            score=float(row.score),
            tier=tier_value,
            top_3_risk_factors=factors,
            recommended_actions=actions,
        )

    async def predict_churn(
        self, customer_ids: list[int], tenant_id: int
    ) -> tuple[list[ChurnPrediction], list[int]]:
        """Batch-compute churn predictions for multiple customers.

        Returns (found, skipped) where ``found`` is a list of predictions in
        the same order as the input IDs and ``skipped`` contains customer
        IDs whose lookup raised NotFoundException.

        Uses 4 batched queries (customer existence, login count, engagement
        diversity, ticket count) plus 1 batched purchase-recency query,
        regardless of batch size.
        """
        if not customer_ids:
            return [], []

        metrics = await self._fetch_raw_metrics_batch(customer_ids, tenant_id)

        found: list[ChurnPrediction] = []
        skipped: list[int] = []
        for cid in customer_ids:
            raw = metrics.get(cid)
            if raw is None:
                skipped.append(cid)
                continue
            name_to_score = {
                "login_frequency": self._normalize_score("login_frequency", raw["login_frequency"]),
                "purchase_recency": self._normalize_score("purchase_recency", raw["purchase_recency_days"]),
                "support_ticket_count": self._normalize_score("support_ticket_count", raw["support_ticket_count"]),
                "engagement_score": self._normalize_score("engagement_score", raw["engagement_score_raw"]),
            }
            raw_total = sum(score * self.WEIGHTS[name] for name, score in name_to_score.items())
            score = round(max(0.0, min(raw_total, 100.0)), 2)

            found.append(
                ChurnPrediction(
                    customer_id=cid,
                    score=score,
                    tier=self._compute_tier(score),
                    top_3_risk_factors=self._build_top_3_factors(name_to_score),
                    recommended_actions=self._build_recommended_actions(raw),
                )
            )

        return found, skipped

    @staticmethod
    def _build_recommended_actions(raw: dict) -> list[str]:
        actions: list[str] = []
        if raw["support_ticket_count"] > 2:
            actions.append("优先处理客户工单，降低流失风险")
        if raw["purchase_recency_days"] > 60:
            actions.append("客户长期无购买记录，触发重新激活营销")
        if raw["login_frequency"] < 3:
            actions.append("客户登录频率低，建议发送个性化内容激活")
        if not actions:
            actions.append("客户状态健康，维持常规维护")
        return actions

    async def _fetch_raw_metrics_batch(
        self, customer_ids: list[int], tenant_id: int
    ) -> dict[int, dict]:
        """Batch-read raw metrics for multiple customers with 4 queries total.

        Returns a dict mapping customer_id -> raw metrics dict. Customers
        not present in the dict do not exist (or are filtered out by tenant).
        """
        now = datetime.now(UTC)
        login_window = now - timedelta(days=30)

        customer_result = await self.session.execute(
            select(CustomerModel.id).where(
                and_(CustomerModel.id.in_(customer_ids), CustomerModel.tenant_id == tenant_id)
            )
        )
        existing_ids = {row[0] for row in customer_result.all()}

        login_result = await self.session.execute(
            select(ActivityModel.customer_id, func.count(ActivityModel.id))
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id.in_(customer_ids),
                    ActivityModel.created_at >= login_window,
                )
            )
            .group_by(ActivityModel.customer_id)
        )
        login_counts = {row[0]: int(row[1] or 0) for row in login_result.all()}

        engagement_result = await self.session.execute(
            select(
                ActivityModel.customer_id,
                func.count(func.distinct(ActivityModel.type)),
            )
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id.in_(customer_ids),
                    ActivityModel.created_at >= login_window,
                )
            )
            .group_by(ActivityModel.customer_id)
        )
        engagement_counts = {row[0]: int(row[1] or 0) for row in engagement_result.all()}

        purchase_result = await self.session.execute(
            select(
                OpportunityModel.customer_id,
                func.max(OpportunityModel.created_at),
            )
            .where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id.in_(customer_ids),
                    OpportunityModel.stage == "won",
                )
            )
            .group_by(OpportunityModel.customer_id)
        )
        last_purchase_by_customer: dict[int, datetime] = {}
        for row in purchase_result.all():
            cid = row[0]
            last = row[1]
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            last_purchase_by_customer[cid] = last

        ticket_result = await self.session.execute(
            select(TicketModel.customer_id, func.count(TicketModel.id))
            .where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.customer_id.in_(customer_ids),
                    TicketModel.status.in_(("open", "pending")),
                )
            )
            .group_by(TicketModel.customer_id)
        )
        ticket_counts = {row[0]: int(row[1] or 0) for row in ticket_result.all()}

        metrics: dict[int, dict] = {}
        for cid in customer_ids:
            if cid not in existing_ids:
                continue
            last_purchase = last_purchase_by_customer.get(cid)
            if last_purchase is not None:
                purchase_recency_days = max(0.0, (now - last_purchase).total_seconds() / 86400.0)
            else:
                purchase_recency_days = 90
            metrics[cid] = {
                "login_frequency": login_counts.get(cid, 0),
                "purchase_recency_days": purchase_recency_days,
                "support_ticket_count": ticket_counts.get(cid, 0),
                "engagement_score_raw": engagement_counts.get(cid, 0),
            }
        return metrics
