import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
sys.path.insert(0, '/home/runner/work/agent-job/agent-job/src')
sys.path.insert(0, '/home/runner/work/agent-job/agent-job/tests/unit')

from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.tickets import make_ticket_handler
from tests.unit.domain_handlers.ticket_categorization import make_ticket_categorization_handler
from src.services.ticket_categorization_service import TicketCategorizationService
from src.internal.ai_gateway import AIResponse
from src.pkg.errors.app_exceptions import NotFoundException

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

mock_db_session = make_mock_session(
    [
        make_ticket_handler(state),
        make_ticket_categorization_handler(state),
    ],
    state=state,
)

mock_gateway = AsyncMock()
mock_gateway.chat.return_value = AIResponse(reply="billing", suggestions=[], actions=[])

service = TicketCategorizationService(mock_db_session, mock_gateway)

class TestDebug:
    async def test_await_direct(self):
        """Direct await - this works"""
        with pytest.raises(NotFoundException):
            await asyncio.sleep(0)

    async def test_await_raise_direct(self):
        """Raise directly inside await - should pass"""
        with pytest.raises(NotFoundException):
            await asyncio.sleep(0)
            raise NotFoundException('Ticket')

    async def test_await_raise_nested(self):
        """Raise from inner coroutine inside await - this works"""
        async def inner():
            raise NotFoundException('Ticket')
        with pytest.raises(NotFoundException):
            await inner()

    async def test_await_with_mock(self):
        """Await a mock that raises - does this work?"""
        exc_mock = AsyncMock(side_effect=NotFoundException('Ticket'))
        with pytest.raises(NotFoundException):
            await exc_mock()

    async def test_service_pattern(self):
        """Exact service pattern - does it work?"""
        with pytest.raises(NotFoundException):
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)
