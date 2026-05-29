"""Copilot service — builds system prompts from CRM context and exposes a tool registry."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException
from services.churn_prediction import ChurnPredictionService


class CopilotService:
    """Builds CRM-aware system prompts and manages a copilot tool registry."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_customer(self, tenant_id: int, customer_id: int) -> CustomerModel:
        result = await self.session.execute(
            select(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("客户")
        return row

    async def _get_opportunities(self, tenant_id: int, customer_id: int) -> list[OpportunityModel]:
        result = await self.session.execute(
            select(OpportunityModel).where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.customer_id == customer_id,
                )
            )
        )
        return list(result.scalars().all())

    async def _get_recent_activities(self, tenant_id: int, customer_id: int, limit: int = 10) -> list[ActivityModel]:
        result = await self.session.execute(
            select(ActivityModel)
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                )
            )
            .order_by(ActivityModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_system_prompt(self, tenant_id: int, customer_id: int) -> str:
        customer = await self._get_customer(tenant_id, customer_id)
        opportunities = await self._get_opportunities(tenant_id, customer_id)
        activities = await self._get_recent_activities(tenant_id, customer_id)

        lines = [
            f"Customer: {customer.name} | Status: {customer.status} | Owner: {customer.owner_id} | Tags: {customer.tags}"
        ]
        for opp in opportunities:
            lines.append(
                f"Opportunity: {opp.name} | Stage: {opp.stage} | "
                f"Amount: {opp.amount} | Prob: {opp.probability}% | "
                f"Expected Close: {opp.expected_close_date}"
            )
        for act in activities:
            lines.append(f"Activity[{act.type}]: {act.content or ''} at {act.created_at}")
        return "\n".join(lines)

    async def persist_message(self, tenant_id: int, role: str, content: str) -> None:
        """Persist a conversation message. DB write is deferred until the message schema is defined."""
        # TODO: Replace with ConversationMessageModel insert once schema is finalized (issue #505).
        return

    def get_tool_registry(self) -> dict[str, dict]:
        """Return the copilot tool registry dict."""

        async def get_customer_handler(tenant_id: int, customer_id: int):
            return await self._get_customer(tenant_id, customer_id)

        async def get_opportunities_handler(tenant_id: int, customer_id: int):
            return await self._get_opportunities(tenant_id, customer_id)

        async def get_recent_activities_handler(tenant_id: int, customer_id: int):
            return await self._get_recent_activities(tenant_id, customer_id)

        async def get_churn_risk_handler(tenant_id: int, customer_id: int):
            return await ChurnPredictionService(self.session).get_churn_prediction(customer_id, tenant_id)

        return {
            "get_customer": {
                "description": "Retrieve a customer record by customer_id",
                "handler": get_customer_handler,
                "deferred": False,
            },
            "get_opportunities": {
                "description": "List all opportunities for a customer",
                "handler": get_opportunities_handler,
                "deferred": False,
            },
            "get_recent_activities": {
                "description": "List recent activities for a customer",
                "handler": get_recent_activities_handler,
                "deferred": False,
            },
            "get_churn_risk": {
                "description": "Get churn risk prediction for a customer",
                "handler": get_churn_risk_handler,
                "deferred": False,
            },
            "send_email": {
                "description": "TBD — deferred: email sending tool not yet implemented",
                "handler": None,
                "deferred": True,
            },
            "create_task": {
                "description": "TBD — deferred: task creation tool not yet implemented",
                "handler": None,
                "deferred": True,
            },
        }
