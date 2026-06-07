"""Unit tests for src/api/routers/ai_chat.py — AI Chat router endpoint tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.ai_chat import ai_chat_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def client_with_service(monkeypatch, mock_db_session):
    """Return a TestClient with AIService fully mocked."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    mock_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.ai_chat.AIService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(ai_chat_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_db_session

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/ai/chat
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_send_message_with_conversation_id(self, client_with_service):
        client, svc = client_with_service

        mock_response = MagicMock()
        mock_response.reply = "你好，这是AI助手。"
        mock_response.suggestions = ["查看客户列表", "创建工单"]
        mock_response.actions = []
        svc.send_message = AsyncMock(return_value=mock_response)

        resp = client.post("/api/v1/ai/chat", json={"message": "你好", "conversation_id": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["reply"] == "你好，这是AI助手。"
        assert body["data"]["suggestions"] == ["查看客户列表", "创建工单"]
        svc.send_message.assert_called_once()
        call_kwargs = svc.send_message.call_args.kwargs
        assert call_kwargs["conversation_id"] == 5
        assert call_kwargs["message"] == "你好"
        assert call_kwargs["tenant_id"] == 1
        assert call_kwargs["user_id"] == 99

    def test_auto_create_conversation_when_no_id(self, client_with_service):
        client, svc = client_with_service

        mock_conv = MagicMock()
        mock_conv.id = 42
        svc.create_conversation = AsyncMock(return_value=mock_conv)

        mock_response = MagicMock()
        mock_response.reply = "Hello!"
        mock_response.suggestions = None
        mock_response.actions = None
        svc.send_message = AsyncMock(return_value=mock_response)

        resp = client.post("/api/v1/ai/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["reply"] == "Hello!"
        svc.create_conversation.assert_called_once_with(
            tenant_id=1, user_id=99, title=None
        )
        svc.send_message.assert_called_once()
        call_kwargs = svc.send_message.call_args.kwargs
        assert call_kwargs["conversation_id"] == 42

    def test_empty_message_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/ai/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_message_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/ai/chat", json={"message": "x" * 4001})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/ai/sessions
# ---------------------------------------------------------------------------

class TestSessionsEndpoint:
    def test_list_sessions_returns_paginated_items(self, client_with_service):
        client, svc = client_with_service

        mock_conv1 = MagicMock()
        mock_conv1.to_dict.return_value = {
            "id": 1, "tenant_id": 1, "user_id": 99, "title": "Chat A",
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
        }
        mock_conv2 = MagicMock()
        mock_conv2.to_dict.return_value = {
            "id": 2, "tenant_id": 1, "user_id": 99, "title": "Chat B",
            "created_at": "2026-01-02T00:00:00", "updated_at": "2026-01-02T00:00:00",
        }
        svc.list_conversations = AsyncMock(return_value=([mock_conv1, mock_conv2], 2))

        resp = client.get("/api/v1/ai/sessions?page=1&page_size=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["items"]) == 2
        assert body["data"]["total"] == 2
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20
        assert body["data"]["total_pages"] == 1

        svc.list_conversations.assert_called_once_with(
            tenant_id=1, user_id=99, page=1, page_size=20
        )

    def test_page_zero_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/ai/sessions?page=0")
        assert resp.status_code == 422

    def test_page_size_over_limit_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/ai/sessions?page_size=101")
        assert resp.status_code == 422

    def test_default_pagination(self, client_with_service):
        client, svc = client_with_service

        svc.list_conversations = AsyncMock(return_value=([], 0))

        resp = client.get("/api/v1/ai/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20

        svc.list_conversations.assert_called_once_with(
            tenant_id=1, user_id=99, page=1, page_size=20
        )