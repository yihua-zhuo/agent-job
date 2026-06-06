"""Unit tests for EventService — service-layer validation and DB behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pkg.errors.app_exceptions import ValidationException
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
        """All event types in VALID_EVENT_TYPES are accepted by the service (exact equality)."""
        assert set(VALID_EVENT_TYPES) == {"email_open", "website_visit"}

        for event_type in VALID_EVENT_TYPES:
            session = MagicMock()
            session.add = MagicMock()
            session.flush = AsyncMock()
            session.refresh = AsyncMock()
            # Customer existence check returns a row -> customer exists -> insert proceeds
            existence_result = MagicMock()
            existence_result.scalar_one_or_none.return_value = 1
            session.execute = AsyncMock(return_value=existence_result)
            svc = EventService(session)
            await svc.record_engagement_event(
                tenant_id=1,
                customer_id=1,
                event_type=event_type,
            )
            session.add.assert_called_once()
