"""AI Chat Assistant service — conversation management and CRM-context injection."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.ai_conversation import AIConversationModel, AIMessageModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from db.models.task import TaskModel
from db.models.ticket import TicketModel
from internal.ai_gateway import AIChatGateway, AIResponse
from pkg.errors.app_exceptions import NotFoundException


class AIService:
    """Conversation management and AI gateway orchestration."""

    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        self.session = session
        self.gateway = gateway or AIChatGateway()

    # -------------------------------------------------------------------------
    # Conversation CRUD
    # -------------------------------------------------------------------------

    async def create_conversation(
        self, tenant_id: int, user_id: int, title: str | None = None
    ) -> AIConversationModel:
        """Create a new AI conversation record."""
        now = datetime.now(UTC)
        conversation = AIConversationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: int, tenant_id: int) -> AIConversationModel:
        """Fetch a conversation, raising NotFoundException if missing or tenant-scoped."""
        result = await self.session.execute(
            select(AIConversationModel).where(
                and_(
                    AIConversationModel.id == conversation_id,
                    AIConversationModel.tenant_id == tenant_id,
                )
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException("Conversation")
        return conversation

    async def list_conversations(
        self, tenant_id: int, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[AIConversationModel], int]:
        """Return paginated conversations for a tenant+user."""
        offset = (page - 1) * page_size

        count_result = await self.session.execute(
            select(func.count(AIConversationModel.id)).where(
                and_(
                    AIConversationModel.tenant_id == tenant_id,
                    AIConversationModel.user_id == user_id,
                )
            )
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            select(AIConversationModel)
            .where(
                and_(
                    AIConversationModel.tenant_id == tenant_id,
                    AIConversationModel.user_id == user_id,
                )
            )
            .order_by(AIConversationModel.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        conversations = result.scalars().all()
        return list(conversations), int(total)

    async def get_conversation_messages(
        self, conversation_id: int, tenant_id: int, limit: int = 100
    ) -> list[AIMessageModel]:
        """Return ordered messages for a conversation."""
        result = await self.session.execute(
            select(AIMessageModel)
            .where(
                and_(
                    AIMessageModel.conversation_id == conversation_id,
                    AIMessageModel.tenant_id == tenant_id,
                )
            )
            .order_by(AIMessageModel.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Chat
    # -------------------------------------------------------------------------

    async def send_message(
        self,
        conversation_id: int,
        message: str,
        tenant_id: int,
        user_id: int,
    ) -> AIResponse:
        """Store user message, call AI gateway with CRM context, store & return reply."""
        # Ensure the conversation belongs to this tenant
        await self.get_conversation(conversation_id, tenant_id)

        # Persist user message
        now = datetime.now(UTC)
        user_msg = AIMessageModel(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role="user",
            content=message,
            created_at=now,
        )
        self.session.add(user_msg)
        await self.session.flush()

        # Build chat history for gateway
        messages = await self._build_message_history(conversation_id, tenant_id)

        # Enrich with CRM context
        context = await self._enrich_context(tenant_id, user_id)

        # Call AI gateway
        reply_response = await self.gateway.chat(messages, context)

        # Persist assistant reply
        assistant_msg = AIMessageModel(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role="assistant",
            content=reply_response.reply,
            created_at=datetime.now(UTC),
        )
        self.session.add(assistant_msg)
        await self.session.flush()

        # Update conversation updated_at
        conversation = await self.get_conversation(conversation_id, tenant_id)
        conversation.updated_at = datetime.now(UTC)
        await self.session.flush()

        return reply_response

    async def _build_message_history(
        self, conversation_id: int, tenant_id: int
    ) -> list[dict[str, str]]:
        """Return conversation messages as a list of {role, content} dicts."""
        msgs = await self.get_conversation_messages(conversation_id, tenant_id, limit=50)
        return [{"role": m.role, "content": m.content} for m in msgs]

    # -------------------------------------------------------------------------
    # CRM context enrichment
    # -------------------------------------------------------------------------

    async def _enrich_context(self, tenant_id: int, user_id: int) -> dict[str, Any]:
        """Query CRM entities and return a context dict for the AI gateway."""
        customer_count = await self._count_model(CustomerModel, tenant_id)
        open_ticket_count = await self._count_model(
            TicketModel, tenant_id, extra_where=(TicketModel.status != "closed")
        )
        opportunity_count = await self._count_model(OpportunityModel, tenant_id)
        activity_count = await self._count_model(ActivityModel, tenant_id)
        task_count = await self._count_model(TaskModel, tenant_id)

        # Fetch top 5 recent customers for additional context
        recent_customers = await self._fetch_recent(CustomerModel, tenant_id, limit=5)
        open_tickets = await self._fetch_recent(
            TicketModel, tenant_id, extra_where=(TicketModel.status != "closed"), limit=5
        )

        return {
            "customer_count": customer_count,
            "open_ticket_count": open_ticket_count,
            "opportunity_count": opportunity_count,
            "activity_count": activity_count,
            "task_count": task_count,
            "recent_customers": [c.name for c in recent_customers],
            "open_ticket_subjects": [t.subject for t in open_tickets],
        }

    async def _count_model(self, model, tenant_id: int, extra_where=None):
        where_clause = model.tenant_id == tenant_id
        if extra_where is not None:
            where_clause = and_(where_clause, extra_where)
        result = await self.session.execute(select(func.count(model.id)).where(where_clause))
        return result.scalar() or 0

    async def _fetch_recent(self, model, tenant_id: int, extra_where=None, limit: int = 5):
        where_clause = model.tenant_id == tenant_id
        if extra_where is not None:
            where_clause = and_(where_clause, extra_where)
        result = await self.session.execute(
            select(model).where(where_clause).order_by(model.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
