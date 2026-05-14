"""Unit tests for src/api/routers/ai.py — AI router endpoint tests."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.ai import ai_router, _check_rate_limit, _rate_limit_store, _RATE_LIMIT_MAX
from internal.ai_gateway import AIResponse
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db
from pkg.errors.app_exceptions import NotFoundException, ValidationException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


CONVERSATION_ROW = {
    "id": 1,
    "tenant_id": 1,
    "user_id": 99,
    "title": "Test Chat",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}

MESSAGE_ROWS = [
    {"id": 1, "conversation_id": 1, "tenant_id": 1, "role": "user", "content": "Hello", "created_at": "2026-01-01T00:00:00"},
    {"id": 2, "conversation_id": 1, "tenant_id": 1, "role": "assistant", "content": "Hi there!", "created_at": "2026-01-01T00:01:00"},
]


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with AIService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from pkg.errors.app_exceptions import AppException

    mock_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.ai.AIService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(ai_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


@pytest.fixture(autouse=True)
def clear_rate_limit_store():
    """Clear the global rate limit store before each test."""
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


# ---------------------------------------------------------------------------
# Rate limit helper
# ---------------------------------------------------------------------------

class TestRateLimitHelper:
    def test_passes_up_to_limit(self):
        _rate_limit_store.clear()
        tenant_id = 1
        for _ in range(_RATE_LIMIT_MAX):
            _check_rate_limit(tenant_id)  # Should not raise up to MAX calls
        # MAX+1 should fail
        with pytest.raises(ValidationException) as exc_info:
            _check_rate_limit(tenant_id)
        assert "Rate limit exceeded" in str(exc_info.value.detail)

    def test_different_tenants_independent(self):
        _rate_limit_store.clear()
        # Fill up tenant 1 to the limit
        for _ in range(_RATE_LIMIT_MAX):
            _check_rate_limit(1)
        with pytest.raises(ValidationException):
            _check_rate_limit(1)
        # Tenant 2 should still pass
        _check_rate_limit(2)  # Should not raise


# ---------------------------------------------------------------------------
# POST /api/v1/ai/chat
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_creates_new_conversation_if_no_id(self, client_with_service):
        client, svc = client_with_service
        mock_conv = MagicMock()
        mock_conv.id = 1
        mock_conv.title = None
        mock_conv.created_at = MagicMock()
        mock_conv.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_conv.updated_at = MagicMock()
        mock_conv.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

        svc.create_conversation = AsyncMock(return_value=mock_conv)

        mock_response = MagicMock()
        mock_response.reply = "Hello!"
        mock_response.suggestions = ["Show customers"]
        mock_response.actions = []
        svc.send_message = AsyncMock(return_value=mock_response)

        resp = client.post("/api/v1/ai/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["reply"] == "Hello!"

    def test_uses_existing_conversation_id(self, client_with_service):
        client, svc = client_with_service

        mock_response = MagicMock()
        mock_response.reply = "Reply!"
        mock_response.suggestions = None
        mock_response.actions = None
        svc.send_message = AsyncMock(return_value=mock_response)

        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "Hello", "conversation_id": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # Verify send_message was called with the existing conversation_id
        svc.send_message.assert_called_once()
        call_kwargs = svc.send_message.call_args.kwargs
        assert call_kwargs["conversation_id"] == 5

    def test_empty_message_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/ai/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_message_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/ai/chat", json={"message": "x" * 4001})
        assert resp.status_code == 422

    def test_not_found_conversation_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.create_conversation = AsyncMock(
            side_effect=NotFoundException("Conversation")
        )
        resp = client.post("/api/v1/ai/chat", json={"message": "Hello"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/ai/conversation
# ---------------------------------------------------------------------------

class TestCreateConversationEndpoint:
    def test_creates_conversation_returns_201(self, client_with_service):
        client, svc = client_with_service

        mock_conv = MagicMock()
        mock_conv.id = 42
        mock_conv.title = "My Chat"
        mock_conv.created_at = MagicMock()
        mock_conv.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_conv.updated_at = MagicMock()
        mock_conv.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
        svc.create_conversation = AsyncMock(return_value=mock_conv)

        resp = client.post("/api/v1/ai/conversation", json={"title": "My Chat"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == 42
        assert body["data"]["title"] == "My Chat"

    def test_creates_with_null_title(self, client_with_service):
        client, svc = client_with_service

        mock_conv = MagicMock()
        mock_conv.id = 1
        mock_conv.title = None
        mock_conv.created_at = MagicMock()
        mock_conv.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_conv.updated_at = MagicMock()
        mock_conv.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
        svc.create_conversation = AsyncMock(return_value=mock_conv)

        resp = client.post("/api/v1/ai/conversation", json={})
        assert resp.status_code == 201

    def test_title_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/ai/conversation", json={"title": "x" * 201})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/ai/conversation/{id}
# ---------------------------------------------------------------------------

class TestGetConversationEndpoint:
    def test_returns_conversation_with_messages(self, client_with_service):
        client, svc = client_with_service

        mock_conv = MagicMock()
        mock_conv.id = 1
        mock_conv.title = "Test Chat"
        mock_conv.created_at = MagicMock()
        mock_conv.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_conv.updated_at = MagicMock()
        mock_conv.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

        svc.get_conversation = AsyncMock(return_value=mock_conv)

        mock_msgs = []
        for row in MESSAGE_ROWS:
            msg = MagicMock()
            msg.id = row["id"]
            msg.role = row["role"]
            msg.content = row["content"]
            msg.created_at = MagicMock()
            msg.created_at.isoformat.return_value = row["created_at"]
            mock_msgs.append(msg)

        svc.get_conversation_messages = AsyncMock(return_value=mock_msgs)

        resp = client.get("/api/v1/ai/conversation/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == 1
        assert len(body["data"]["messages"]) == 2

    def test_missing_conversation_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_conversation = AsyncMock(
            side_effect=NotFoundException("Conversation")
        )
        resp = client.get("/api/v1/ai/conversation/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Rate limit integration in endpoints
# ---------------------------------------------------------------------------

class TestRateLimitIntegration:
    def test_rate_limit_exceeded_returns_422(self):
        # Simulate a full rate limit store
        _rate_limit_store.clear()
        for _ in range(30):
            _check_rate_limit(999)

        from internal.middleware.fastapi_auth import require_auth
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from pkg.errors.app_exceptions import AppException

        app = FastAPI()
        app.include_router(ai_router)
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=999)
        app.dependency_overrides[get_db] = lambda: MagicMock()

        @app.exception_handler(AppException)
        async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "message": exc.detail, "code": exc.code},
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/ai/conversation", json={})
        assert resp.status_code == 422
        assert "Rate limit exceeded" in resp.json()["message"]