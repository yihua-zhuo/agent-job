"""
客户流失预测服务 — DB-backed via SQLAlchemy async.

Computes risk scores from real customer/activity/ticket/opportunity data.
"""

from dataclasses import dataclass
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
    """流失风险因素"""

    factor: str
    weight: float
    current_value: float
    description: str


@dataclass
class ChurnPrediction:
    """客户流失预测结果"""

    customer_id: int
    score: float
    risk_level: str
    factors: list[ChurnRiskFactor]


@dataclass
class ChurnAction:
    """客户流失干预建议"""

    action: str
    priority: str
    reason: str


class ChurnPredictionService:
    """客户流失预测服务 — backed by real DB."""

    RISK_FACTORS = [
        "days_since_last_activity",
        "decrease_in_activity",
        "decrease_in_revenue",
        "support_tickets_increase",
        "payment_delays",
        "negative_feedback",
    ]

    FACTOR_WEIGHTS = {
        "days_since_last_activity": 0.20,
        "decrease_in_activity": 0.18,
        "decrease_in_revenue": 0.22,
        "support_tickets_increase": 0.15,
        "payment_delays": 0.15,
        "negative_feedback": 0.10,
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _verify_customer(self, customer_id: int, tenant_id: int) -> CustomerModel:
        result = await self.session.execute(
            select(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")
        return customer

    async def _get_customer_metrics(self, customer_id: int, tenant_id: int) -> dict:
        """Gather metrics for churn calculation from the DB."""
        customer = await self._verify_customer(customer_id, tenant_id)
        now = datetime.now(UTC)

        # days since last activity
        act_result = await self.session.execute(
            select(func.max(ActivityModel.created_at)).where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                )
            )
        )
        last_activity = act_result.scalar()
        if last_activity:
            # Make naive datetime tz-aware for comparison
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            days_since = (now - last_activity).days
        else:
            # No activity ever → fall back to customer's created_at
            created = customer.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            days_since = (now - created).days if created else 90

        # activity trend (last 30 vs 60-30 days prior)
        recent_window = now - timedelta(days=30)
        prior_window = now - timedelta(days=60)
        recent_act = await self.session.execute(
            select(func.count(ActivityModel.id)).where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                    ActivityModel.created_at >= recent_window,
                )
            )
        )
        prior_act = await self.session.execute(
            select(func.count(ActivityModel.id)).where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                    ActivityModel.created_at >= prior_window,
                    ActivityModel.created_at < recent_window,
                )
            )
        )
        recent_count = recent_act.scalar() or 0
        prior_count = prior_act.scalar() or 0
        activity_trend = (recent_count / prior_count) if prior_count > 0 else (0.5 if recent_count == 0 else 1.0)

        # revenue trend (sum of opportunity amounts)
        recent_rev_result = await self.session.execute(
            select(func.coalesce(func.sum(OpportunityModel.amount), 0)).where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id == customer_id,
                    OpportunityModel.created_at >= recent_window,
                )
            )
        )
        prior_rev_result = await self.session.execute(
            select(func.coalesce(func.sum(OpportunityModel.amount), 0)).where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id == customer_id,
                    OpportunityModel.created_at >= prior_window,
                    OpportunityModel.created_at < recent_window,
                )
            )
        )
        recent_rev = float(recent_rev_result.scalar() or 0)
        prior_rev = float(prior_rev_result.scalar() or 0)
        revenue_trend = ((recent_rev - prior_rev) / prior_rev) if prior_rev > 0 else 0.0

        # open ticket count (proxy for support burden)
        tickets_result = await self.session.execute(
            select(func.count(TicketModel.id)).where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.customer_id == customer_id,
                    TicketModel.status.in_(("open", "pending")),
                )
            )
        )
        support_tickets_count = tickets_result.scalar() or 0

        return {
            "customer_id": customer_id,
            "days_since_last_activity": days_since,
            "activity_trend": activity_trend,
            "revenue_trend": revenue_trend,
            "support_tickets_count": support_tickets_count,
            "payment_delays_count": 0,  # not tracked in schema
            "negative_feedback_score": 0.0,  # not tracked in schema
        }

    async def calculate_churn_score(self, customer_id: int, tenant_id: int = 0) -> float:
        """计算流失风险分数 (0-100)"""
        data = await self._get_customer_metrics(customer_id, tenant_id)
        scores = self._compute_scores(data)
        total_score = sum(scores[factor] * self.FACTOR_WEIGHTS[factor] for factor in self.RISK_FACTORS)
        return round(total_score, 2)

    @staticmethod
    def _compute_scores(data: dict) -> dict[str, float]:
        scores = {}
        scores["days_since_last_activity"] = min(data["days_since_last_activity"] / 90 * 100, 100)
        scores["decrease_in_activity"] = max(0, (1.0 - data["activity_trend"]) * 100)
        scores["decrease_in_revenue"] = max(0, (0 - data["revenue_trend"]) * 100)
        scores["support_tickets_increase"] = min(data["support_tickets_count"] / 10 * 100, 100)
        scores["payment_delays"] = min(data["payment_delays_count"] / 5 * 100, 100)
        scores["negative_feedback"] = data["negative_feedback_score"] * 100
        return scores

    async def predict_churn(
        self,
        customer_ids: list[int] | None = None,
        tenant_id: int = 0,
    ) -> list[ChurnPrediction]:
        """批量预测流失风险"""
        if customer_ids is None:
            result = await self.session.execute(
                select(CustomerModel.id).where(CustomerModel.tenant_id == tenant_id).limit(100)
            )
            customer_ids = [row[0] for row in result.fetchall()]

        results = []
        for cid in customer_ids:
            try:
                score = await self.calculate_churn_score(cid, tenant_id)
                factors = await self.get_churn_risk_factors(cid, tenant_id)
            except NotFoundException:
                continue
            results.append(
                ChurnPrediction(
                    customer_id=cid,
                    score=score,
                    risk_level=self._get_risk_level(score),
                    factors=factors,
                )
            )
        return results

    @staticmethod
    def _get_risk_level(score: float) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    async def get_churn_risk_factors(self, customer_id: int, tenant_id: int = 0) -> list[ChurnRiskFactor]:
        """获取流失风险因素详情"""
        data = await self._get_customer_metrics(customer_id, tenant_id)

        current_values = {
            "days_since_last_activity": data["days_since_last_activity"],
            "decrease_in_activity": round(data["activity_trend"] * 100, 2),
            "decrease_in_revenue": round(data["revenue_trend"] * 100, 2),
            "support_tickets_increase": data["support_tickets_count"],
            "payment_delays": data["payment_delays_count"],
            "negative_feedback": round(data["negative_feedback_score"] * 100, 2),
        }

        return [
            ChurnRiskFactor(
                factor=factor,
                weight=self.FACTOR_WEIGHTS[factor],
                current_value=current_values[factor],
                description=factor,
            )
            for factor in self.RISK_FACTORS
        ]

    async def get_high_risk_customers(
        self,
        threshold: float = 70.0,
        tenant_id: int = 0,
    ) -> list[ChurnPrediction]:
        """获取高风险客户列表"""
        all_results = await self.predict_churn(customer_ids=None, tenant_id=tenant_id)
        high_risk = [r for r in all_results if r.score >= threshold]
        high_risk.sort(key=lambda x: x.score, reverse=True)
        return high_risk

    async def recommend_actions(self, customer_id: int, tenant_id: int = 0) -> list[ChurnAction]:
        """根据流失风险推荐行动"""
        data = await self._get_customer_metrics(customer_id, tenant_id)
        score = await self.calculate_churn_score(customer_id, tenant_id)
        risk_level = self._get_risk_level(score)

        actions = []
        if data["days_since_last_activity"] > 30:
            actions.append(
                ChurnAction(
                    action="主动联系客户",
                    priority="high" if risk_level == "high" else "medium",
                    reason=f"客户已 {data['days_since_last_activity']} 天无活动",
                )
            )
        if data["activity_trend"] < 0.3:
            actions.append(
                ChurnAction(
                    action="发送个性化优惠",
                    priority="high" if risk_level == "high" else "medium",
                    reason="活动频率显著下降，需要激活",
                )
            )
        if data["revenue_trend"] < -0.2:
            actions.append(
                ChurnAction(action="提供升级方案", priority="medium", reason="收入呈下降趋势")
            )
        if data["support_tickets_count"] > 5:
            actions.append(
                ChurnAction(
                    action="优先处理客户问题",
                    priority="high",
                    reason=f"客户有 {data['support_tickets_count']} 个未解决工单",
                )
            )

        if not actions:
            actions.append(
                ChurnAction(action="定期维护关系", priority="low", reason="客户状态正常，保持常规维护")
            )

        return actions
