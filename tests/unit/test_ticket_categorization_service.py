"""Unit tests for TicketCategorizationService."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from src.internal.ai_gateway import AIResponse
from src.services.ticket_categorization_service import TicketCategorizationService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.ticket_categorization import make_ticket_categorization_handler
from tests.unit.domain_handlers.tickets import make_ticket_handler


@pytest.fixture
def mock_state():
    state = MockState()
    state.opaque["tickets"] = [
        {
            "id": 10,
            "tenant_id": 1,
            "subject": "Login broken",
            "description": "Cannot log in",
            "status": "open",
            "priority": "medium",
            "customer_id": 1,
            "assignee_id": None,
            "created_at": None,
            "updated_at": None,
        },
    ]
    return state


@pytest.fixture
def mock_db_session(mock_state):
    return make_mock_session(
        [
            make_ticket_handler(mock_state),
            make_ticket_categorization_handler(mock_state),
        ],
        state=mock_state,
    )


@pytest.fixture
def mock_gateway():
    return AsyncMock()


@pytest.fixture
def service(mock_db_session, mock_gateway):
    return TicketCategorizationService(mock_db_session, mock_gateway)


class TestCategorizeTicket:
    async def test_happy_path_parses_technical(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(
            reply="technical — the login page crashes", suggestions=[], actions=[]
        )
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category_type == "technical"
        assert result.confidence == Decimal("0.85")
        assert result.ticket_id == 10
        assert result.tenant_id == 1

    async def test_not_found_raises(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="billing", suggestions=[], actions=[])
        with pytest.raises(NotFoundException):
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)

    async def test_unknown_category_falls_back_to_uncategorized(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="please contact support", suggestions=[], actions=[])
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category_type == "uncategorized"
        assert result.confidence == Decimal("0.5")

    async def test_empty_reply_raises_validation(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="", suggestions=[], actions=[])
        try:
            await service.categorize_ticket(ticket_id=10, tenant_id=1)
        except ValidationException:
            pass  # expected
        else:
            pytest.fail("Expected ValidationException to be raised")
