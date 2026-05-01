"""Unit tests for src/api/routers/tickets.py — /api/v1/tickets and /api/v1/sla endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from models.ticket import TicketStatus, TicketPriority, TicketChannel, SLALevel
from api.routers.tickets import (
    tickets_router,
    _http_status,
    _ticket_to_data,
    _reply_to_data,
)
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_service_response(status=ResponseStatus.SUCCESS, data=None, message="OK"):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    resp.message = message
    return resp


# ---------------------------------------------------------------------------
# Mock ticket / reply objects
# ---------------------------------------------------------------------------

class MockTicket:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)
        self.status = TicketStatus.OPEN if not hasattr(self, 'status') else self.status
        self.priority = TicketPriority.MEDIUM if not hasattr(self, 'priority') else self.priority
        self.channel = TicketChannel.EMAIL if not hasattr(self, 'channel') else self.channel
        self.sla_level = SLALevel.STANDARD if not hasattr(self, 'sla_level') else self.sla_level


class MockReply:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)


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
# _http_status
# ---------------------------------------------------------------------------

class TestHttpStatus:
    def test_success_returns_200(self):
        assert _http_status(ResponseStatus.SUCCESS) == 200

    def test_not_found_returns_404(self):
        assert _http_status(ResponseStatus.NOT_FOUND) == 404

    def test_validation_error_returns_400(self):
        assert _http_status(ResponseStatus.VALIDATION_ERROR) == 400

    def test_unauthorized_returns_401(self):
        assert _http_status(ResponseStatus.UNAUTHORIZED) == 401

    def test_server_error_returns_500(self):
        assert _http_status(ResponseStatus.SERVER_ERROR) == 500

    def test_error_returns_400(self):
        assert _http_status(ResponseStatus.ERROR) == 400


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()
    mock_sla_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.tickets.TicketService",
        lambda session: mock_service,
    )
    monkeypatch.setattr(
        "api.routers.tickets.SLAService",
        lambda session, ticket_service=None: mock_sla_service,
    )

    app = FastAPI()
    app.include_router(tickets_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service, mock_sla_service


# ---------------------------------------------------------------------------
# POST /api/v1/tickets — create ticket
# ---------------------------------------------------------------------------

class TestCreateTicketEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc, _ = client_with_service
        mock_ticket = MockTicket(TICKET_ROW)
        svc.create_ticket = AsyncMock(
            return_value=_make_service_response(data=mock_ticket, message="工单创建成功")
        )
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
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="客户不存在",
            )
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
        assert resp.status_code == 400

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
        mock_list = MagicMock()
        mock_list.items = [mock_ticket]
        mock_list.total = 1
        mock_list.page = 1
        mock_list.page_size = 20
        svc.list_tickets = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1

    def test_service_error_propagates(self, client_with_service):
        client, svc, _ = client_with_service
        svc.list_tickets = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 500

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
        svc.get_ticket = AsyncMock(
            return_value=_make_service_response(data=mock_ticket)
        )
        resp = client.get("/api/v1/tickets/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_ticket = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="工单不存在"
            )
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
        svc.update_ticket = AsyncMock(
            return_value=_make_service_response(data=mock_ticket, message="工单更新成功")
        )
        resp = client.put("/api/v1/tickets/1", json={"subject": "Updated subject"})
        assert resp.status_code == 200
        assert resp.json()["data"]["subject"] == "Updated subject"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_ticket = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="工单不存在"
            )
        )
        resp = client.put("/api/v1/tickets/9999", json={"subject": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/tickets/{ticket_id}/assign — assign ticket
# ---------------------------------------------------------------------------

class TestAssignTicketEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_ticket = AsyncMock(
            return_value=_make_service_response(
                data={"ticket_id": 1, "assignee_id": 5},
                message="工单分配成功",
            )
        )
        resp = client.put(
            "/api/v1/tickets/1/assign",
            json={"assignee_id": 5},
        )
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_ticket = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="工单不存在"
            )
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
        svc.add_reply = AsyncMock(
            return_value=_make_service_response(data=mock_reply, message="回复添加成功")
        )
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
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="工单不存在"
            )
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
        svc.change_status = AsyncMock(
            return_value=_make_service_response(data=mock_ticket, message="状态更新成功")
        )
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
        assert body["data"]["total"] == 1


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
        assert body["data"]["total"] == 1


# ---------------------------------------------------------------------------
# POST /api/v1/tickets/{ticket_id}/auto-assign — auto assign
# ---------------------------------------------------------------------------

class TestAutoAssignEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.auto_assign = AsyncMock(
            return_value=_make_service_response(
                data={"ticket_id": 1, "assignee_id": 3},
                message="自动分配成功",
            )
        )
        resp = client.post("/api/v1/tickets/1/auto-assign")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.auto_assign = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="工单不存在"
            )
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
        svc.get_ticket = AsyncMock(
            return_value=_make_service_response(data=mock_ticket)
        )
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
        assert body["data"]["total"] == 1