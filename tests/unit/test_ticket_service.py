"""Unit tests for TicketService."""
import pytest
import pytest_asyncio
from services.ticket_service import TicketService


@pytest.fixture
def ticket_service():
    return TicketService()


@pytest_asyncio.fixture
async def sample_ticket():
    """Return a fixed mock ticket ID without touching the database."""
    return 1


@pytest.mark.asyncio
class TestTicketService:
    async def test_create_ticket(self, ticket_service):
        result = await ticket_service.create_ticket(
            subject="New Ticket",
            description="Description here",
            customer_id=1,
            channel="email",
            priority="high",
            tenant_id=1,
        )
        assert bool(result) is True
        assert result.data["subject"] == "New Ticket"
        assert result.data["priority"] == "high"

    async def test_get_ticket(self, ticket_service, sample_ticket):
        result = await ticket_service.get_ticket(sample_ticket, tenant_id=1)
        assert bool(result) is True
        assert result.data["subject"] == "Sample Ticket"

    async def test_update_ticket(self, ticket_service, sample_ticket):
        result = await ticket_service.update_ticket(
            sample_ticket,
            {"subject": "Updated Title"},
            tenant_id=1,
        )
        assert bool(result) is True
        assert result.data["subject"] == "Updated Title"

    async def test_assign_ticket(self, ticket_service, sample_ticket):
        result = await ticket_service.assign_ticket(sample_ticket, assignee_id=5, tenant_id=1)
        assert bool(result) is True
        assert result.data["assignee_id"] == 5

    async def test_add_reply(self, ticket_service, sample_ticket):
        result = await ticket_service.add_reply(
            sample_ticket,
            content="This is a reply",
            author_id=1,
            tenant_id=1,
        )
        assert bool(result) is True
        assert result.data["content"] == "This is a reply"

    async def test_change_status(self, ticket_service, sample_ticket):
        result = await ticket_service.change_status(sample_ticket, "resolved", tenant_id=1)
        assert bool(result) is True
        assert result.data["status"] == "resolved"

    async def test_get_customer_tickets(self, ticket_service):
        await ticket_service.create_ticket(
            title="Ticket for Customer 1",
            description="Desc",
            priority="low",
            channel="feature",
            tenant_id=1,
            customer_id=10,
        )
        result = await ticket_service.get_customer_tickets(10, tenant_id=1)
        assert bool(result) is True
        assert all(t["customer_id"] == 10 for t in result.data["items"])

    async def test_list_tickets(self, ticket_service):
        result = await ticket_service.list_tickets(tenant_id=1)
        assert bool(result) is True

    async def test_change_status_to_resolved(self, ticket_service, sample_ticket):
        result = await ticket_service.change_status(sample_ticket, "resolved", tenant_id=1)
        assert bool(result) is True
        assert result.data["status"] == "resolved"

    async def test_create_ticket_minimal_fields(self, ticket_service):
        result = await ticket_service.create_ticket(
            title="Minimal Ticket",
            description="Desc",
            tenant_id=1,
        )
        assert bool(result) is True

    async def test_get_nonexistent_ticket(self, ticket_service):
        result = await ticket_service.get_ticket(99999, tenant_id=1)
        assert bool(result) is False

    async def test_update_nonexistent_ticket(self, ticket_service):
        result = await ticket_service.update_ticket(99999, {"subject": "X"}, tenant_id=1)
        assert bool(result) is False

    async def test_assign_nonexistent_ticket(self, ticket_service):
        result = await ticket_service.assign_ticket(99999, assignee_id=1, tenant_id=1)
        assert bool(result) is False

    async def test_add_reply_nonexistent_ticket(self, ticket_service):
        result = await ticket_service.add_reply(
            99999, content="Reply", author_id=1, tenant_id=1
        )
        assert bool(result) is False

    async def test_add_internal_reply(self, ticket_service, sample_ticket):
        result = await ticket_service.add_reply(
            sample_ticket, content="Internal note", author_id=1, is_internal=True, tenant_id=1
        )
        assert bool(result) is True

    async def test_change_status_nonexistent_ticket(self, ticket_service):
        result = await ticket_service.change_status(99999, "open", tenant_id=1)
        assert bool(result) is False

    async def test_list_tickets_with_status_filter(self, ticket_service):
        result = await ticket_service.list_tickets(tenant_id=1, status="open")
        assert bool(result) is True

    async def test_list_tickets_with_priority_filter(self, ticket_service):
        result = await ticket_service.list_tickets(tenant_id=1, priority="high")
        assert bool(result) is True

    async def test_list_tickets_pagination(self, ticket_service):
        result = await ticket_service.list_tickets(tenant_id=1, page=1, page_size=5)
        assert bool(result) is True
        assert result.data.page == 1
        assert result.data.page_size == 5
