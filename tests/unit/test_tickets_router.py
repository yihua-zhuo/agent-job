"""Unit tests for src/api/routers/tickets.py — /api/v1/tickets and /api/v1/sla endpoints."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.tickets import tickets_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from models.ticket import SLALevel, TicketChannel, TicketPriority, TicketStatus
from pkg.errors.app_exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


# ---------------------------------------------------------------------------
# Mock ticket / reply objects with to_dict()
# ---------------------------------------------------------------------------

class MockTicket:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)
        self.status = TicketStatus.OPEN if not hasattr(self, 'status') else self.status
        self.priority = TicketPriority.MEDIUM if not hasattr(self, 'priority') else self.priority
        self.channel = TicketChannel.EMAIL if not hasattr(self, 'channel') else self.channel
        self.sla_level = SLALevel.STANDARD if not hasattr(self, 'sla_level') else self.sla_level

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "subject": getattr(self, "subject", None),
            "description": getattr(self, "description", None),
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "priority": self.priority.value if hasattr(self.priority, 'value') else self.priority,
            "channel": self.channel.value if hasattr(self.channel, 'value') else self.channel,
            "customer_id": getattr(self, "customer_id", None),
            "assigned_to": getattr(self, "assigned_to", None),
            "sla_level": self.sla_level.value if hasattr(self.sla_level, 'value') else self.sla_level,
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
            "resolved_at": getattr(self, "resolved_at", None),
            "first_response_at": getattr(self, "first_response_at", None),
            "response_deadline": getattr(self, "response_deadline", None),
        }


class MockReply:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "ticket_id": getattr(self, "ticket_id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "content": getattr(self, "content", None),
            "is_internal": getattr(self, "is_internal", False),
            "created_by": getattr(self, "created_by", None),
            "created_at": getattr(self, "created_at", None),
        }


TICKET_ROW = {
    "id": 1,
    "tenant_id": 1,
    "subject": "Help needed",
    "description": "I need assistance",
    "status": TicketStatus.OPEN,
    "priority": TicketPriority.MEDIUM,
    "channel": TicketChannel.EMAIL,
    "customer_id": 1,
    "assigned_to": None,
    "sla_level": SLALevel.STANDARD,
    "created_at": None,
    "updated_at": None,
    "resolved_at": None,
    "first_response_at": None,
    "response_deadline": None,
}


REPLY_ROW = {
    "id": 1,
    "ticket_id": 1,
    "tenant_id": 1,
    "content": "Here is the response",
    "is_internal": False,
    "created_by": 99,
    "created_at": None,
}


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()
    mock_sla_service = MagicMock()
    mock_user_service = MagicMock()
    mock_user_service.get_user_by_id = AsyncMock(return_value=object())

    monkeypatch.setattr(
        "api.routers.tickets.TicketService",
        lambda session: mock_service,
    )
    monkeypatch.setattr(
        "api.routers.tickets.SLAService",
        lambda session, ticket_service=None: mock_sla_service,
    )
    monkeypatch.setattr(
        "api.routers.tickets.UserService",
        lambda session: mock_user_service,
    )

    app = FastAPI()
    app.include_router(tickets_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    # raise_server_exceptions=False so 500s surface as HTTP responses, not exceptions
    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service, mock_sla_service


# ---------------------------------------------------------------------------
# POST /api/v1/tickets — create ticket
# ---------------------------------------------------------------------------

class TestCreateTicketEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.create_ticket = AsyncMock(return_value=mock_ticket)
        resp = client.post(
            "/api/v1/tickets",
            json={
                "subject": "Help needed",
                "description": "I need assistance",
                "customer_id": 1,
                "channel": "email",
                "priority": "medium",
                "sla_level": "standard",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["subject"] == "Help needed"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc, _ = client_with_service
        svc.create_ticket = AsyncMock(
            side_effect=ValidationException("客户不存在")
        )
        resp = client.post(
            "/api/v1/tickets",
            json={
                "subject": "Help",
                "description": "Desc",
                "customer_id": 9999,
                "channel": "email",
            },
        )
        assert resp.status_code == 422

    def test_invalid_channel_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.post(
            "/api/v1/tickets",
            json={
                "subject": "Help",
                "description": "Desc",
                "customer_id": 1,
                "channel": "invalid_channel",
            },
        )
        assert resp.status_code == 422

    def test_invalid_priority_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.post(
            "/api/v1/tickets",
            json={
                "subject": "Help",
                "description": "Desc",
                "customer_id": 1,
                "channel": "email",
                "priority": "super-high",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tickets — list tickets
# ---------------------------------------------------------------------------

class TestListTicketsEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.list_tickets = AsyncMock(return_value=([mock_ticket], 1))
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.get("/api/v1/tickets?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{ticket_id} — get ticket
# ---------------------------------------------------------------------------

class TestGetTicketEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.get_ticket = AsyncMock(return_value=mock_ticket)
        resp = client.get("/api/v1/tickets/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_ticket = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.get("/api/v1/tickets/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/tickets/{ticket_id} — update ticket
# ---------------------------------------------------------------------------

class TestUpdateTicketEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        updated_row = {**TICKET_ROW, "subject": "Updated subject"}
        mock_ticket = MockTicket(updated_row)
        svc.update_ticket = AsyncMock(return_value=mock_ticket)
        resp = client.put("/api/v1/tickets/1", json={"subject": "Updated subject"})
        assert resp.status_code == 200
        assert resp.json()["data"]["subject"] == "Updated subject"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_ticket = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.put("/api/v1/tickets/9999", json={"subject": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/tickets/{ticket_id}/assign — assign ticket
# ---------------------------------------------------------------------------

class TestAssignTicketEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket({**TICKET_ROW, "assigned_to": 5})
        svc.assign_ticket = AsyncMock(return_value=mock_ticket)
        resp = client.put(
            "/api/v1/tickets/1/assign",
            json={"assignee_id": 5},
        )
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_ticket = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.put("/api/v1/tickets/9999/assign", json={"assignee_id": 5})
        assert resp.status_code == 404

    def test_assignee_id_zero_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/tickets/1/assign", json={"assignee_id": 0})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/tickets/{ticket_id}/replies — add reply
# ---------------------------------------------------------------------------

class TestAddReplyEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc, _ = client_with_service
        mock_reply = MockReply(REPLY_ROW)
        svc.add_reply = AsyncMock(return_value=mock_reply)
        resp = client.post(
            "/api/v1/tickets/1/replies",
            json={
                "content": "Here is the response",
                "created_by": 99,
                "is_internal": False,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["content"] == "Here is the response"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.add_reply = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.post(
            "/api/v1/tickets/9999/replies",
            json={"content": "Hello", "created_by": 99},
        )
        assert resp.status_code == 404

    def test_empty_content_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.post(
            "/api/v1/tickets/1/replies",
            json={"content": "", "created_by": 99},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/v1/tickets/{ticket_id}/status — change status
# ---------------------------------------------------------------------------

class TestChangeTicketStatusEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        updated_row = {**TICKET_ROW, "status": TicketStatus.RESOLVED}
        mock_ticket = MockTicket(updated_row)
        svc.change_status = AsyncMock(return_value=mock_ticket)
        resp = client.put(
            "/api/v1/tickets/1/status",
            json={"new_status": "resolved"},
        )
        assert resp.status_code == 200

    def test_invalid_status_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/tickets/1/status", json={"new_status": "invalid"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/customer/{customer_id} — customer tickets
# ---------------------------------------------------------------------------

class TestGetCustomerTicketsEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.get_customer_tickets = AsyncMock(return_value=[mock_ticket])
        resp = client.get("/api/v1/tickets/customer/1")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/sla/breaches — SLA breaches
# ---------------------------------------------------------------------------

class TestSlaBreachesEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.get_sla_breaches = AsyncMock(return_value=[mock_ticket])
        resp = client.get("/api/v1/tickets/sla/breaches")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1


# ---------------------------------------------------------------------------
# POST /api/v1/tickets/{ticket_id}/auto-assign — auto assign
# ---------------------------------------------------------------------------

class TestAutoAssignEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket({**TICKET_ROW, "assigned_to": 3})
        svc.auto_assign = AsyncMock(return_value=mock_ticket)
        resp = client.post("/api/v1/tickets/1/auto-assign")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.auto_assign = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.post("/api/v1/tickets/9999/auto-assign")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/sla/status/{ticket_id} — SLA status
# ---------------------------------------------------------------------------

class TestSLAStatusEndpoint:
    def test_success(self, client_with_service):
        client, svc, sla_svc = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.get_ticket = AsyncMock(return_value=mock_ticket)
        sla_svc.check_sla_status = AsyncMock(return_value="ok")
        sla_svc.calculate_remaining_time = AsyncMock(
            return_value=MagicMock(total_seconds=MagicMock(return_value=7200))
        )
        resp = client.get("/api/v1/sla/status/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["ticket_id"] == 1
        assert body["data"]["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /api/v1/sla/breaches — SLA breach tickets via SLA router
# ---------------------------------------------------------------------------

class TestSlaBreachTicketsEndpoint:
    def test_success(self, client_with_service):
        client, svc, sla_svc = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        sla_svc.get_breach_tickets = AsyncMock(return_value=[mock_ticket])
        resp = client.get("/api/v1/sla/breaches")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{ticket_id}/replies — get ticket replies
# ---------------------------------------------------------------------------

class TestGetTicketRepliesEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_reply = MockReply(REPLY_ROW)
        svc.get_ticket_replies = AsyncMock(return_value=[mock_reply])
        resp = client.get("/api/v1/tickets/1/replies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["content"] == "Here is the response"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_ticket_replies = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.get("/api/v1/tickets/9999/replies")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{ticket_id}/activity — get ticket activity log
# ---------------------------------------------------------------------------

class MockActivity:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "customer_id": getattr(self, "customer_id", None),
            "opportunity_id": getattr(self, "opportunity_id", None),
            "type": getattr(self, "type", None),
            "content": getattr(self, "content", None),
            "created_by": getattr(self, "created_by", None),
            "created_at": getattr(self, "created_at", None),
        }


ACTIVITY_ROW = {
    "id": 1,
    "tenant_id": 1,
    "customer_id": 1,
    "opportunity_id": None,
    "type": "comment",
    "content": "ticket#1 updated",
    "created_by": 99,
    "created_at": None,
}


class TestGetTicketActivityEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.get_ticket_activity = AsyncMock(return_value=[mock_activity])
        resp = client.get("/api/v1/tickets/1/activity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "comment"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_ticket_activity = AsyncMock(
            side_effect=NotFoundException("Ticket")
        )
        resp = client.get("/api/v1/tickets/9999/activity")
        assert resp.status_code == 404
