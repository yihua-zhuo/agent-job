import pytest
import asyncio
from unittest.mock import AsyncMock
import sys
sys.path.insert(0, '/home/runner/work/agent-job/agent-job/src')
sys.path.insert(0, '/home/runner/work/agent-job/agent-job/tests/unit')

from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.tickets import make_ticket_handler
from src.services.ticket_categorization_service import TicketCategorizationService
from src.internal.ai_gateway import AIResponse
from src.pkg.errors.app_exceptions import NotFoundException

state = MockState()
state.opaque["tickets"] = []

mock_db_session = make_mock_session(
    [make_ticket_handler(state)],
    state=state,
)
mock_gateway = AsyncMock()
mock_gateway.chat.return_value = AIResponse(reply="billing", suggestions=[], actions=[])

service = TicketCategorizationService(mock_db_session, mock_gateway)

async def wrapper():
    """Exactly like service.categorize_ticket but inlined"""
    from sqlalchemy import and_, select
    from src.db.models.ticket import TicketModel
    
    result = await mock_db_session.execute(
        select(TicketModel).where(
            and_(TicketModel.id == 9999, TicketModel.tenant_id == 1)
        )
    )
    ticket = result.scalar_one_or_none()
    print(f"ticket={ticket}")
    if ticket is None:
        raise NotFoundException("Ticket")
    return ticket

class TestDebug:
    async def test_direct_inlined(self):
        """Inlined version of service method - does try/except catch?"""
        exc_caught = False
        try:
            await wrapper()
        except NotFoundException:
            exc_caught = True
        assert exc_caught

    async def test_service_call(self):
        """Direct service call"""
        exc_caught = False
        try:
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)
        except NotFoundException:
            exc_caught = True
        assert exc_caught
