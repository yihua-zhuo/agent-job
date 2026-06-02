import pytest
import asyncio
from unittest.mock import AsyncMock
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
    async def test_service_with_try_except(self):
        print("TEST: before try")
        exc_caught = False
        try:
            print("TRY: before await")
            result = await service.categorize_ticket(ticket_id=9999, tenant_id=1)
            print(f"TRY: after await, result={result}")
        except NotFoundException as e:
            print(f"TRY: except NotFoundException as e: {e}")
            exc_caught = True
        except Exception as e:
            print(f"TRY: except Exception as e: {type(e).__name__} {e}")
        finally:
            print("TRY: finally")
        print(f"TEST: after try, exc_caught={exc_caught}")
        assert exc_caught, "Expected NotFoundException to be caught"

    async def test_simple_raise(self):
        print("SIMPLE: before try")
        try:
            print("SIMPLE: inside try")
            raise NotFoundException("Ticket")
        except NotFoundException:
            print("SIMPLE: caught!")
