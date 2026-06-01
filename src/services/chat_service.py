"""Chat service — intent classification and multi-entity search helpers."""

from __future__ import annotations

import re
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from db.models.ticket import TicketModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException

Intent = Literal["customer_lookup", "sales_summary", "ticket_query", "general"]

# Ordered list of (intent, compiled_regex) pairs — first match wins.
_INTENT_REGEX_PATTERNS: list[tuple[Intent, re.Pattern[str]]] = [
    ("customer_lookup", re.compile(r"\b(customer|customers)\b", re.IGNORECASE)),
    ("ticket_query", re.compile(r"\b(ticket|tickets|support|issue|bug)\b", re.IGNORECASE)),
    ("sales_summary", re.compile(r"\b(deal|deals|opportunity|opportunities|forecast|pipeline|revenue)\b", re.IGNORECASE)),
]

# Keyword-based fallback map: intent -> list of keywords (longest keyword wins).
_INTENT_KEYWORD_MAP: dict[Intent, list[str]] = {
    "customer_lookup": ["customer", "customers"],
    "ticket_query": ["ticket", "support", "issue", "bug"],
    "sales_summary": ["deal", "deals", "opportunity", "opportunities", "forecast", "pipeline", "revenue"],
}


def _escape_like(value: str) -> str:
    """Escape special LIKE characters."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ChatService:
    """Intent classification and database query helpers for chat."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def classify_intent(self, text: str) -> Intent:
        """Classify the user's message intent using regex first, then keyword fallback.

        Args:
            text: The raw user message.

        Returns:
            One of: "customer_lookup", "ticket_query", "sales_summary", "general".

        Raises:
            ValidationException: If text is empty or whitespace-only.
        """
        if not text or not text.strip():
            raise ValidationException("text cannot be empty")

        # Regex-first: first pattern to match wins.
        for intent, pattern in _INTENT_REGEX_PATTERNS:
            if pattern.search(text):
                return intent

        # Keyword fallback: longest keyword wins.
        lower_text = text.lower()
        best_intent: Intent = "general"
        best_len = 0
        for intent, keywords in _INTENT_KEYWORD_MAP.items():
            for kw in keywords:
                if len(kw) > best_len and kw in lower_text:
                    best_len = len(kw)
                    best_intent = intent
        return best_intent

    async def query_customers(
        self,
        tenant_id: int,
        keyword: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search customers by name/email within a tenant.

        Args:
            tenant_id: Tenant scope.
            keyword: Optional ILIKE search term applied to name and email.
            limit: Maximum rows to return (1–200).

        Returns:
            List of customer dicts ordered by created_at descending.

        Raises:
            ValidationException: If limit is out of range.
        """
        if limit <= 0 or limit > 200:
            raise ValidationException("limit must be between 1 and 200")

        conditions = [CustomerModel.tenant_id == tenant_id]
        if keyword:
            escaped = _escape_like(keyword)
            conditions.append(
                or_(
                    CustomerModel.name.ilike(f"%{escaped}%", escape="\\"),
                    CustomerModel.email.ilike(f"%{escaped}%", escape="\\"),
                )
            )

        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.desc())
            .limit(limit)
        )
        return [r.to_dict() for r in result.scalars().all()]

    async def query_opportunities(
        self,
        tenant_id: int,
        keyword: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search opportunities by name (and numeric customer_id) within a tenant.

        Args:
            tenant_id: Tenant scope.
            keyword: Optional ILIKE search term on name; if all digits, also filters
                     by customer_id.
            limit: Maximum rows to return (1–200).

        Returns:
            List of opportunity dicts ordered by created_at descending.

        Raises:
            ValidationException: If limit is out of range.
        """
        if limit <= 0 or limit > 200:
            raise ValidationException("limit must be between 1 and 200")

        conditions = [OpportunityModel.tenant_id == tenant_id]
        if keyword:
            escaped = _escape_like(keyword)
            name_condition = OpportunityModel.name.ilike(f"%{escaped}%", escape="\\")
            if keyword.isdigit():
                conditions.append(
                    or_(name_condition, OpportunityModel.customer_id == int(keyword))
                )
            else:
                conditions.append(name_condition)

        result = await self.session.execute(
            select(OpportunityModel)
            .where(and_(*conditions))
            .order_by(OpportunityModel.created_at.desc())
            .limit(limit)
        )
        return [r.to_dict() for r in result.scalars().all()]

    async def query_tickets(
        self,
        tenant_id: int,
        keyword: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search tickets by subject/description (and optional status) within a tenant.

        Args:
            tenant_id: Tenant scope.
            keyword: Optional ILIKE search term on subject and description.
            status: Optional exact status filter.
            limit: Maximum rows to return (1–200).

        Returns:
            List of ticket dicts ordered by created_at descending.

        Raises:
            ValidationException: If limit is out of range.
        """
        if limit <= 0 or limit > 200:
            raise ValidationException("limit must be between 1 and 200")

        conditions = [TicketModel.tenant_id == tenant_id]
        if status:
            conditions.append(TicketModel.status == status)
        if keyword:
            escaped = _escape_like(keyword)
            conditions.append(
                or_(
                    TicketModel.subject.ilike(f"%{escaped}%", escape="\\"),
                    TicketModel.description.ilike(f"%{escaped}%", escape="\\"),
                )
            )

        result = await self.session.execute(
            select(TicketModel)
            .where(and_(*conditions))
            .order_by(TicketModel.created_at.desc())
            .limit(limit)
        )
        return [r.to_dict() for r in result.scalars().all()]

    async def handle_message(self, text: str, tenant_id: int) -> dict:
        """Classify a message, dispatch to the appropriate query helper, and return structured result.

        Args:
            text: The raw user message.
            tenant_id: Tenant scope for database queries.

        Returns:
            Dict with keys ``intent``, ``query_results``, and ``error``.
            ``query_results`` is None when intent is ``general`` or an error occurred.
        """
        if not text or not text.strip():
            return {"intent": "general", "query_results": None, "error": "empty message"}

        intent = await self.classify_intent(text)
        results: list[dict] | None = None
        error: str | None = None

        try:
            if intent == "customer_lookup":
                results = await self.query_customers(tenant_id, keyword=text)
            elif intent == "sales_summary":
                results = await self.query_opportunities(tenant_id, keyword=text)
            elif intent == "ticket_query":
                results = await self.query_tickets(tenant_id, keyword=text)
            # "general" → no DB query
        except (NotFoundException, ValidationException) as exc:
            error = str(exc.detail)

        return {"intent": intent, "query_results": results, "error": error}
