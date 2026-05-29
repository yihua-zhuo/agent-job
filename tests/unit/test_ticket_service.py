"""Unit tests for src/services/ticket_service.py."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.ticket_service import TicketService


class MockTicketModel:
    """Minimal mock matching TicketModel interface."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.tenant_id = kwargs.get("tenant_id", 1)
        self.subject = kwargs.get("subject", "Test ticket")
        self.description = kwargs.get("description", "Description")
        self.status = kwargs.get("status", "open")
        self.priority = kwargs.get("priority", "medium")
        self.channel = kwargs.get("channel", "email")
        self.customer_id = kwargs.get("customer_id", 1)
        self.assigned_to = kwargs.get("assigned_to", None)
        self.sla_level = kwargs.get("sla_level", "standard")
        self.resolved_at = kwargs.get("resolved_at", None)
        self.first_response_at = kwargs.get("first_response_at", None)
        self.response_deadline = kwargs.get("response_deadline", None)
        self.created_at = kwargs.get("created_at", datetime.now(UTC))
        self.updated_at = kwargs.get("updated_at", datetime.now(UTC))

    def check_sla_breach(self):
        if self.resolved_at:
            return False
        if self.response_deadline is None:
            return False
        return datetime.now(UTC) > self.response_deadline


class MockReplyModel:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.ticket_id = kwargs.get("ticket_id", 1)
        self.tenant_id = kwargs.get("tenant_id", 1)
        self.content = kwargs.get("content", "Reply content")
        self.is_internal = kwargs.get("is_internal", False)
        self.created_by = kwargs.get("created_by", 99)
        self.created_at = kwargs.get("created_at", datetime.now(UTC))

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "is_internal": self.is_internal,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MockActivityModel:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.tenant_id = kwargs.get("tenant_id", 1)
        self.customer_id = kwargs.get("customer_id", 1)
        self.opportunity_id = kwargs.get("opportunity_id", None)
        self.type = kwargs.get("type", "comment")
        self.content = kwargs.get("content", "Activity content")
        self.created_by = kwargs.get("created_by", 99)
        self.created_at = kwargs.get("created_at", datetime.now(UTC))

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "opportunity_id": self.opportunity_id,
            "type": self.type,
            "content": self.content,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MockResult:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._call_count = 0

    def scalars(self):
        class _Scalars:
            def __init__(self, rows):
                self._rows = rows
            def all(self):
                return self._rows
        return _Scalars(self._rows)

    def scalar_one_or_none(self):
        self._call_count += 1
        return self._rows[0] if self._rows else None


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def ticket_service(mock_session):
    return TicketService(mock_session)


# ---------------------------------------------------------------------------
# get_ticket_replies
# ---------------------------------------------------------------------------

class TestGetTicketReplies:
    async def test_returns_replies_ordered_by_created_at_asc(self, ticket_service, mock_session):
        reply1 = MockReplyModel(id=1, ticket_id=1, content="First reply")
        reply2 = MockReplyModel(id=2, ticket_id=1, content="Second reply")
        ticket_row = MockTicketModel(id=1)
        # First call: _fetch (existence check); Second call: replies query
        mock_session.execute.side_effect = [MockResult([ticket_row]), MockResult([reply1, reply2])]

        result = await ticket_service.get_ticket_replies(ticket_id=1, tenant_id=1)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
        assert mock_session.execute.call_count == 2
        # Verify last call (replies query) contains order by asc
        calls = mock_session.execute.call_args_list
        last_call = calls[-1]
        sql_str = str(last_call[0][0]).lower()
        assert "order by" in sql_str
        assert "asc" in sql_str

    async def test_raises_not_found_for_invalid_ticket(self, ticket_service, mock_session):
        mock_session.execute.side_effect = [MockResult([]), MockResult([])]

        from pkg.errors.app_exceptions import NotFoundException
        with pytest.raises(NotFoundException):
            await ticket_service.get_ticket_replies(ticket_id=9999, tenant_id=1)


# ---------------------------------------------------------------------------
# get_ticket_activity
# ---------------------------------------------------------------------------

class TestGetTicketActivity:
    @pytest.mark.asyncio
    async def test_returns_activity_ordered_by_created_at_desc(self, ticket_service, mock_session):
        activity1 = MockActivityModel(id=1, content="ticket#1 updated")
        activity2 = MockActivityModel(id=2, content="ticket#1 assigned")
        ticket_row = MockTicketModel(id=1)
        mock_session.execute.side_effect = [MockResult([ticket_row]), MockResult([activity1, activity2])]

        result = await ticket_service.get_ticket_activity(ticket_id=1, tenant_id=1)

        assert len(result) == 2
        assert mock_session.execute.call_count == 2
        # Verify last call (activity query) contains order by desc
        calls = mock_session.execute.call_args_list
        last_call = calls[-1]
        sql_str = str(last_call[0][0]).lower()
        assert "order by" in sql_str
        assert "desc" in sql_str

    @pytest.mark.asyncio
    async def test_raises_not_found_for_invalid_ticket(self, ticket_service, mock_session):
        mock_session.execute.side_effect = [MockResult([]), MockResult([])]

        from pkg.errors.app_exceptions import NotFoundException
        with pytest.raises(NotFoundException):
            await ticket_service.get_ticket_activity(ticket_id=9999, tenant_id=1)


# ---------------------------------------------------------------------------
# SLA breach detection
# ---------------------------------------------------------------------------

class TestSLABreachDetection:
    def test_breached_when_deadline_passed_and_not_resolved(self):
        ticket = MockTicketModel(
            resolved_at=None,
            response_deadline=datetime.now(UTC) - timedelta(hours=1),
        )
        assert ticket.check_sla_breach() is True

    def test_not_breached_when_resolved(self):
        ticket = MockTicketModel(
            resolved_at=datetime.now(UTC),
            response_deadline=datetime.now(UTC) - timedelta(hours=1),
        )
        assert ticket.check_sla_breach() is False

    def test_not_breached_when_deadline_not_set(self):
        ticket = MockTicketModel(
            resolved_at=None,
            response_deadline=None,
        )
        assert ticket.check_sla_breach() is False

    def test_not_breached_when_deadline_in_future(self):
        ticket = MockTicketModel(
            resolved_at=None,
            response_deadline=datetime.now(UTC) + timedelta(hours=1),
        )
        assert ticket.check_sla_breach() is False
