"""Ticket categorization service — LLM-based classification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, case, func, select
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
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_metrics(self, tenant_id: int) -> dict:
        total_result = await self.session.execute(
            select(
                func.count(TicketCategorizationModel.id).label("total"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(
                    case((TicketCategorizationModel.human_override, 1), else_=0)
                ).label("override_count"),
            ).where(TicketCategorizationModel.tenant_id == tenant_id)
        )
        row = total_result.one()
        total = row.total or 0
        override_count = int(row.override_count or 0)
        override_rate = override_count / total if total > 0 else 0.0

        type_result = await self.session.execute(
            select(
                TicketCategorizationModel.category_type,
                func.count(TicketCategorizationModel.id).label("count"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(
                    case((TicketCategorizationModel.human_override, 1), else_=0)
                ).label("overrides"),
            )
            .where(TicketCategorizationModel.tenant_id == tenant_id)
            .group_by(TicketCategorizationModel.category_type)
        )
        by_type = {
            r.category_type: {
                "count": r.count,
                "avg_confidence": round(float(r.avg_confidence), 4),
                "overrides": int(r.overrides or 0),
            }
            for r in type_result
        }

        priority_result = await self.session.execute(
            select(
                TicketCategorizationModel.priority,
                func.count(TicketCategorizationModel.id).label("count"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(
                    case((TicketCategorizationModel.human_override, 1), else_=0)
                ).label("overrides"),
            )
            .where(TicketCategorizationModel.tenant_id == tenant_id)
            .group_by(TicketCategorizationModel.priority)
        )
        by_priority = {
            r.priority: {
                "count": r.count,
                "avg_confidence": round(float(r.avg_confidence), 4),
                "overrides": int(r.overrides or 0),
            }
            for r in priority_result
        }

        return {
            "total_categorized": total,
            "override_count": override_count,
            "override_rate": round(float(override_rate), 4),
            "average_confidence": round(float(row.avg_confidence or 0.0), 4),
            "by_type": by_type,
            "by_priority": by_priority,
        }
