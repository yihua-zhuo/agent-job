"""Ticket categorization service — LLM-based classification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ticket import TicketModel
from db.models.ticket_categorization import TicketCategorizationModel
from internal.ai_gateway import AIChatGateway, AIResponse
from pkg.errors.app_exceptions import NotFoundException, ValidationException

_CATEGORY_KEYWORDS = {
    "billing": ["billing", "invoice", "payment", "charge", "refund"],
    "technical": ["technical", "bug", "error", "crash", "not working", "broken"],
    "sales": ["sales", "pricing", "quote", "demo", "purchase"],
    "feature_request": ["feature", "request", "suggest", "improve", "would like"],
    "account": ["account", "login", "password", "access", "permission"],
    "general": ["general", "other", "question", "inquiry"],
}
_DEFAULT_CATEGORY = "uncategorized"
_DEFAULT_CONFIDENCE = 0.5


def _parse_category_from_reply(reply: str) -> tuple[str, float]:
    reply_lower = reply.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in reply_lower for kw in keywords):
            return category, 0.85
    return _DEFAULT_CATEGORY, _DEFAULT_CONFIDENCE


class TicketCategorizationService:
    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None) -> None:
        if session is None:
            raise TypeError("session is required, no default")
        self.session = session
        self.gateway = gateway or AIChatGateway()

    async def categorize_ticket(self, ticket_id: int, tenant_id: int) -> TicketCategorizationModel:
        result = await self.session.execute(
            select(TicketModel).where(and_(TicketModel.id == ticket_id, TicketModel.tenant_id == tenant_id))
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise NotFoundException("Ticket")

        subject = ticket.subject or ""
        description = ticket.description or ""
        prompt = (
            "Classify this support ticket. Respond with only the category name "
            "(billing, technical, sales, feature_request, account, or general).\n\n"
            f"Subject: {subject}\nDescription: {description}"
        )

        ai_response: AIResponse = await self.gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            context={},
        )

        if not ai_response.reply or not ai_response.reply.strip():
            raise ValidationException("AI gateway returned empty response")

        category, confidence = _parse_category_from_reply(ai_response.reply)

        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            category_type=category,
            confidence=Decimal(str(confidence)),
            reasons={"reasoning": ai_response.reply[:500]} if ai_response.reply else None,
            human_override=False,
            categorized_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
