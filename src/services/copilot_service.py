"""Copilot service — builds system prompts from CRM context and exposes a tool registry."""

import asyncio

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.conversation import ConversationModel
from db.models.conversation_message import ConversationMessageModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from internal.ai_gateway import AIChatGateway, AIResponse
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
    # Conversation management
    # ------------------------------------------------------------------

    async def get_or_create_conversation(
        self,
        tenant_id: int,
        user_id: int,
        channel: str = "copilot",
    ) -> ConversationModel:
        """Return the most recent conversation for tenant+user, creating one if none exist."""
        result = await self.session.execute(
            select(ConversationModel)
            .where(
                and_(
                    ConversationModel.tenant_id == tenant_id,
                    ConversationModel.user_id == user_id,
                )
            )
            .order_by(ConversationModel.id.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            conversation = ConversationModel(
                tenant_id=tenant_id,
                user_id=user_id,
                channel=channel,
            )
            self.session.add(conversation)
            await self.session.flush()
        return conversation

    async def get_conversation(self, conversation_id: int, tenant_id: int) -> ConversationModel:
        """Fetch a single conversation, raising NotFoundException if missing or belongs to another tenant."""
        result = await self.session.execute(
            select(ConversationModel).where(
                and_(
                    ConversationModel.id == conversation_id,
                    ConversationModel.tenant_id == tenant_id,
                )
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Conversation")
        return conversation

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

    async def persist_message(
        self,
        conversation_id: int,
        tenant_id: int,
        role: str,
        content: str,
    ) -> None:
        """Persist a conversation message to the database."""
        msg = ConversationMessageModel(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=role,
            content=content,
        )
        self.session.add(msg)
        await self.session.flush()

    async def get_history(self, conversation_id: int, tenant_id: int) -> tuple[list[ConversationMessageModel], int]:
        """Return (messages, total_count) for a conversation, newest first, capped at 20."""
        count_result = await self.session.execute(
            select(func.count(ConversationMessageModel.id)).where(
                and_(
                    ConversationMessageModel.conversation_id == conversation_id,
                    ConversationMessageModel.tenant_id == tenant_id,
                )
            )
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(ConversationMessageModel)
            .where(
                and_(
                    ConversationMessageModel.conversation_id == conversation_id,
                    ConversationMessageModel.tenant_id == tenant_id,
                )
            )
            .order_by(ConversationMessageModel.created_at.desc(), ConversationMessageModel.id.desc())
            .limit(20)
        )
        messages = list(result.scalars().all())
        return messages, total

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

    async def chat(
        self,
        tenant_id: int,
        user_id: int,
        message: str,
    ) -> AIResponse:
        """Persist user message, invoke AI, persist assistant reply, return AI response.

        This is the single entry point for the copilot chat flow. The router calls
        no other service methods for this workflow.
        """
        conversation = await self.get_or_create_conversation(
            tenant_id=tenant_id,
            user_id=user_id,
            channel="copilot",
        )
        await self.persist_message(
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            role="user",
            content=message,
        )
        messages_history, _ = await self.get_history(conversation.id, tenant_id=tenant_id)
        history_msgs = [{"role": m.role, "content": m.content} for m in reversed(messages_history)]
        history_msgs.append({"role": "user", "content": message})
        ai_response = await self.invoke_ai(history_msgs, tenant_id=tenant_id)
        await self.persist_message(
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            role="assistant",
            content=ai_response.reply,
        )
        return ai_response

    async def invoke_ai(self, messages: list[dict[str, str]], tenant_id: int | None = None) -> AIResponse:
        """Invoke the AI chat gateway with the given message history.

        A 30-second timeout is applied so slow/hung AI responses do not block
        the request event loop indefinitely (Rule 44 / Rule 131).

        Args:
            messages: List of ``{"role": "user"|"assistant", "content": "..."}`` entries.
            tenant_id: Tenant owning this conversation (reserved for future context injection;
                not currently used by the gateway stub).

        Returns:
            AIResponse with reply, optional suggestions, and optional actions.
        """
        gateway = AIChatGateway()
        return await asyncio.wait_for(gateway.chat(messages), timeout=30)
