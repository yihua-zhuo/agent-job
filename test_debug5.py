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
state.opaque["tickets"] = []

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
    async def test_service_not_found(self):
        """The service pattern that fails in the real test"""
        try:
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)
        except NotFoundException:
            print("EXCEPTION CAUGHT!")
            assert True
            return
        pytest.fail("Expected NotFoundException to be raised")

    async def test_service_not_found_inline(self):
        """Inline version"""
        with pytest.fail("testing"):
            try:
                await service.categorize_ticket(ticket_id=9999, tenant_id=1)
            except NotFoundException:
                print("CAUGHT IN INLINE")
                raise
        print("AFTER inline test")

    async def test_manual_raise(self):
        """Manual raise pattern"""
        exc_caught = False
        try:
            try:
                raise NotFoundException('Ticket')
            except NotFoundException:
                exc_caught = True
                print("Inner caught")
                raise
        except NotFoundException:
            print("Outer caught")
            exc_caught = exc_caught and True
        assert exc_caught
