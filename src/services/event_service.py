"""EventService — records customer engagement events."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.engagement import EngagementEventModel
from pkg.errors.app_exceptions import ValidationException

VALID_EVENT_TYPES = {"email_open", "website_visit"}


class EventService:
    """Business logic for engagement events — persists EngagementEventModel rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_engagement_event(
        self,
        tenant_id: int,
        customer_id: int,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> EngagementEventModel:
        """Insert a new engagement event and return the refreshed ORM object.

        Flushes so the auto-generated id is populated, but does not commit —
        the router-owned transaction boundary (Rule 121) commits on normal
        exit. Callers that invoke this service outside a router context must
        commit the session themselves if they need the row visible to
        subsequent reads.
        """
        if event_type not in VALID_EVENT_TYPES:
            raise ValidationException(f"event_type must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}")
        event = EngagementEventModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event
