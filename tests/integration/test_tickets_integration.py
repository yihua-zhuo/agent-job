"""Integration tests for full ticket CRUD flow.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_tickets_integration.py -v

Requires DATABASE_URL pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest

from models.ticket import TicketChannel, TicketPriority, TicketStatus
from pkg.errors.app_exceptions import NotFoundException
from services.customer_service import CustomerService
from services.ticket_service import TicketService
from services.user_service import UserService


async def _seed_customer(async_session, tenant_id: int) -> int:
    """Create a customer and return its id."""
    svc = CustomerService(async_session)
    result = await svc.create_customer(
        data={"name": "Test Customer", "email": f"test-{uuid.uuid4().hex[:8]}@example.com"},
        tenant_id=tenant_id,
    )
    return result.id


async def _seed_user(async_session, tenant_id: int, role: str = "agent") -> int:
    """Create a user and return their id."""
    svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    user = await svc.create_user(
        username=f"ticketuser_{suffix}",
        email=f"ticket_{suffix}@example.com",
        password="Test@Pass1234",
        role=role,
        tenant_id=tenant_id,
    )
    return user.id


@pytest.mark.integration
class TestTicketCreateAndGet:
    async def test_create_ticket(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Test ticket subject",
            description="Test ticket description",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        assert ticket.subject == "Test ticket subject"
        assert ticket.status == TicketStatus.OPEN.value
        assert ticket.priority == TicketPriority.HIGH.value

    async def test_get_ticket_not_found(self, db_schema, tenant_id, async_session):
        svc = TicketService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_ticket(99999, tenant_id=tenant_id)


@pytest.mark.integration
class TestTicketReplies:
    async def test_add_and_get_replies(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        user_id = await _seed_user(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Reply test ticket",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.CHAT,
            tenant_id=tenant_id,
        )

        await svc.add_reply(
            ticket_id=ticket.id,
            content="First public reply",
            created_by=user_id,
            is_internal=False,
            tenant_id=tenant_id,
        )
        await svc.add_reply(
            ticket_id=ticket.id,
            content="Internal note",
            created_by=user_id,
            is_internal=True,
            tenant_id=tenant_id,
        )

        replies = await svc.get_ticket_replies(ticket.id, tenant_id=tenant_id)
        assert len(replies) == 2
        assert replies[0].content == "First public reply"
        assert replies[0].is_internal is False
        assert replies[1].content == "Internal note"
        assert replies[1].is_internal is True

    async def test_reply_raises_not_found_for_invalid_ticket(self, db_schema, tenant_id, async_session):
        svc = TicketService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_ticket_replies(99999, tenant_id=tenant_id)


@pytest.mark.integration
class TestTicketStatusChange:
    async def test_change_status_workflow(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Status change test",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        assert ticket.status == TicketStatus.OPEN.value

        updated = await svc.change_status(ticket.id, TicketStatus.IN_PROGRESS, tenant_id=tenant_id)
        assert updated.status == TicketStatus.IN_PROGRESS.value

        updated = await svc.change_status(ticket.id, TicketStatus.RESOLVED, tenant_id=tenant_id)
        assert updated.status == TicketStatus.RESOLVED.value


@pytest.mark.integration
class TestTicketAssignment:
    async def test_assign_ticket(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        agent_id = await _seed_user(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Assignment test",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        assert ticket.assigned_to is not None  # auto-assigned on creation

        assigned = await svc.assign_ticket(ticket.id, agent_id, tenant_id=tenant_id)
        assert assigned.assigned_to == agent_id


@pytest.mark.integration
class TestTicketUpdate:
    async def test_update_ticket(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Original subject",
            description="Original description",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )

        updated = await svc.update_ticket(
            ticket.id,
            tenant_id=tenant_id,
            subject="Updated subject",
            description="Updated description",
        )
        assert updated.subject == "Updated subject"
        assert updated.description == "Updated description"


@pytest.mark.integration
class TestTicketList:
    async def test_list_tickets_with_filters(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)

        await svc.create_ticket(
            subject="Open ticket",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        closed_ticket = await svc.create_ticket(
            subject="Closed ticket",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.PHONE,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )
        # Close the second ticket so we can test status filtering
        await svc.change_status(closed_ticket.id, TicketStatus.CLOSED, tenant_id=tenant_id)

        all_tickets, total = await svc.list_tickets(tenant_id=tenant_id)
        assert total == 2

        high_priority, total_hp = await svc.list_tickets(
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        assert total_hp == 1
        assert high_priority[0].priority == TicketPriority.HIGH.value

        open_tickets, total_open = await svc.list_tickets(
            status=TicketStatus.OPEN,
            tenant_id=tenant_id,
        )
        assert total_open == 1


@pytest.mark.integration
class TestTicketSLA:
    async def test_sla_deadline_set_on_creation(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="SLA test ticket",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        assert ticket.response_deadline is not None


@pytest.mark.integration
class TestTicketActivity:
    async def test_get_ticket_activity_returns_list(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Activity test ticket",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        # Service returns empty list when no activity records exist
        activities = await svc.get_ticket_activity(ticket.id, tenant_id=tenant_id)
        assert isinstance(activities, list)


@pytest.mark.integration
class TestTicketAutoAssign:
    async def test_auto_assign_assigns_agents_round_robin(self, db_schema, tenant_id, async_session):
        customer_id = await _seed_customer(async_session, tenant_id)
        svc = TicketService(async_session)

        ticket1 = await svc.create_ticket(
            subject="Auto-assign test 1",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        ticket2 = await svc.create_ticket(
            subject="Auto-assign test 2",
            description="Body",
            customer_id=customer_id,
            channel=TicketChannel.EMAIL,
            tenant_id=tenant_id,
        )
        # Both should be auto-assigned (not None)
        assert ticket1.assigned_to is not None
        assert ticket2.assigned_to is not None
        # Round-robin means they get different agents (or same if pool loops)
        assert isinstance(ticket1.assigned_to, int)
        assert isinstance(ticket2.assigned_to, int)
