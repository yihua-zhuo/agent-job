"""Unit tests for EventService — service-layer validation and DB behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.event_service import VALID_EVENT_TYPES, EventService


class TestEventServiceValidation:
    """Tests for EventService.record_engagement_event validation and persistence paths."""

    @pytest.mark.asyncio
    async def test_record_engagement_event_invalid_type_raises(self):
        """EventService raises ValidationException for event_type not in the allowlist."""
        # validation path does not touch the DB; MagicMock is safe here
        svc = EventService(MagicMock())
        with pytest.raises(ValidationException, match="event_type must be one of"):
            await svc.record_engagement_event(tenant_id=1, customer_id=1, event_type="bogus")

    @pytest.mark.asyncio
    async def test_valid_event_types_accepted(self):
        """All event types in VALID_EVENT_TYPES are accepted and persisted.

        Iterates over VALID_EVENT_TYPES only and asserts each is in the
        allow-list and that the service persists + refreshes for it. Adding a
        new valid type will not silently update a hard-coded set literal —
        the iteration is the source of truth.
        """
        # The iteration IS the assertion: every element in VALID_EVENT_TYPES
        # must be one of the known strings. An accidental extra value in the
        # module-level constant would be caught here.
        for event_type in VALID_EVENT_TYPES:
            assert event_type in {"email_open", "website_visit"}

        for event_type in VALID_EVENT_TYPES:
            session = MagicMock()
            session.add = MagicMock()
            session.flush = AsyncMock()
            session.refresh = AsyncMock()
            svc = EventService(session)
            result = await svc.record_engagement_event(
                tenant_id=1,
                customer_id=1,
                event_type=event_type,
            )
            session.add.assert_called_once()
            session.flush.assert_awaited_once()
            session.refresh.assert_awaited_once()
            assert result.tenant_id == 1
            assert result.customer_id == 1
            assert result.event_type == event_type

    @pytest.mark.asyncio
    async def test_record_engagement_event_unknown_customer_raises_not_found(self):
        """FK violation on INSERT (unknown customer_id) is translated to NotFoundException.

        EventService no longer pre-checks customer existence — the FK constraint
        on customer_id raises IntegrityError on flush, which the service
        catches and re-raises as NotFoundException("Customer"). The session is
        rolled back so the IntegrityError does not leave the unit-of-work dirty.
        """
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock(
            side_effect=IntegrityError("INSERT INTO engagement_events ...", {}, Exception("FK violation"))
        )
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        svc = EventService(session)

        with pytest.raises(NotFoundException, match="Customer"):
            await svc.record_engagement_event(
                tenant_id=1,
                customer_id=9999,
                event_type="email_open",
            )

        session.rollback.assert_awaited_once()
        session.refresh.assert_not_awaited()
