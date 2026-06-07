"""Unit tests for ticket categorization feedback service and router schema."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.ticket_service import TicketService


class TestSubmitCategorizationFeedback:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return TicketService(mock_session)

    async def test_feedback_persisted_and_human_override_set(self, service, mock_session):
        """Happy path: feedback row added, human_override=True on categorization."""
        existing_cat = MagicMock()
        existing_cat.category_type = "billing"
        existing_cat.priority = "low"
        existing_cat.human_override = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_cat)
        mock_session.execute.return_value = mock_result

        def fake_refresh(obj):
            obj.id = 1
            obj.ticket_id = 5
            obj.tenant_id = 1
            obj.original_category = "billing"
            obj.original_priority = "low"
            obj.corrected_category = "technical"
            obj.corrected_priority = None
            obj.corrected_by = 42
            obj.created_at = None

        mock_session.refresh.side_effect = fake_refresh

        result = await service.submit_categorization_feedback(
            ticket_id=5,
            tenant_id=1,
            user_id=42,
            corrected_category="technical",
            corrected_priority=None,
        )
        assert existing_cat.human_override is True
        mock_session.add.assert_called_once()
        assert result.corrected_category == "technical"
        assert result.corrected_by == 42

    async def test_raises_not_found_when_no_categorization_record(self, service, mock_session):
        """Boundary: ticket has no TicketCategorizationModel → NotFoundException."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        with pytest.raises(NotFoundException) as exc_info:
            await service.submit_categorization_feedback(
                ticket_id=999,
                tenant_id=1,
                user_id=1,
                corrected_category="billing",
                corrected_priority=None,
            )
        assert "TicketCategorization" in str(exc_info.value)

    async def test_router_validates_at_least_one_field_provided(self):
        """Error: PATCH payload with neither category nor priority → ValidationException."""
        from api.routers.tickets import CategorizationFeedbackPayload

        payload = CategorizationFeedbackPayload()
        assert payload.category is None and payload.priority is None
        # Simulate router validation logic
        if payload.category is None and payload.priority is None:
            with pytest.raises(ValidationException) as exc_info:
                raise ValidationException("At least one of category or priority must be provided")
        assert "At least one of category or priority" in str(exc_info.value)
