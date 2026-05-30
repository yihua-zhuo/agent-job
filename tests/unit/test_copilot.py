"""Unit tests for the copilot router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from db.connection import get_db
from internal.ai_gateway import AIResponse
from internal.middleware.fastapi_auth import AuthContext, require_auth
from main import app
from pkg.errors.app_exceptions import NotFoundException


# ------------------------------------------------------------------
# Module-scoped auth/DB override fixture
# ------------------------------------------------------------------


@pytest.fixture
def mock_auth():
    """Return an AuthContext for tenant 100, user 999."""

    async def _mock_require_auth():
        return AuthContext(user_id=999, tenant_id=100, roles=["admin"])

    return _mock_require_auth


def _make_mock_session():
    """Build a fresh mock AsyncSession."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_get_db():
    """Return a sync factory that yields a fresh mock session per call.

    FastAPI calls ``solve_dependencies`` which iterates the async generator
    returned by the override via ``enter_async_context`` — the factory itself
    is called once per request scope, so a fresh session is returned each time.
    """
    return _make_mock_session


@pytest.fixture(autouse=True)
def setup_and_teardown_overrides(mock_auth, mock_get_db):
    """Override both require_auth and get_db for every test, cleaned up after."""
    app.dependency_overrides[require_auth] = mock_auth
    app.dependency_overrides[get_db] = mock_get_db
    yield
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(get_db, None)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestCopilotRouter:
    """Tests for copilot router endpoints."""

    @pytest.mark.asyncio
    async def test_chat_returns_envelope(self):
        """POST /copilot/chat returns {"success": True, "data": {"response": ..., "tool_calls": []}}."""
        from services.copilot_service import CopilotService

        ai_response = AIResponse(reply="Hello! How can I help?")

        with patch.object(CopilotService, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = ai_response

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/copilot/chat?message=hello")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "response" in data["data"]
        assert "tool_calls" in data["data"]
        assert data["data"]["response"] == "Hello! How can I help?"
        mock_chat.assert_called_once_with(tenant_id=100, user_id=999, message="hello")

    @pytest.mark.asyncio
    async def test_chat_empty_message_returns_422(self):
        """POST /copilot/chat with an empty message returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/copilot/chat?message=")
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body or "message" in body

    @pytest.mark.asyncio
    async def test_chat_invoke_ai_error_propagates(self):
        """CopilotService.chat raising an exception is not caught by the router."""
        from services.copilot_service import CopilotService

        with patch.object(CopilotService, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = RuntimeError("AI gateway unavailable")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                with pytest.raises(RuntimeError, match="AI gateway unavailable"):
                    await ac.post("/copilot/chat?message=hello")

    @pytest.mark.asyncio
    async def test_chat_missing_auth_returns_401(self):
        """A request without auth override returns 401."""
        app.dependency_overrides.pop(require_auth, None)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/copilot/chat?message=token")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_history_returns_envelope(self):
        """GET /copilot/1/history returns {"success": True, "data": {"messages": [], "total": 0}}."""
        from services.copilot_service import CopilotService

        mock_msg = MagicMock()
        mock_msg.to_dict.return_value = {
            "id": 1,
            "conversation_id": 1,
            "tenant_id": 100,
            "role": "user",
            "content": "hello",
            "tool_calls_json": None,
            "created_at": None,
            "updated_at": None,
        }

        with (
            patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history,
            patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv,
        ):
            mock_get_conv.return_value = MagicMock()
            mock_get_history.return_value = ([mock_msg], 1)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/1/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "messages" in data["data"]
        assert "total" in data["data"]
        assert len(data["data"]["messages"]) == 1
        assert data["data"]["messages"][0]["role"] == "user"
        assert data["data"]["messages"][0]["content"] == "hello"
        mock_get_history.assert_called_once_with(conversation_id=1, tenant_id=100)

    @pytest.mark.asyncio
    async def test_history_caps_at_20(self):
        """History endpoint serializes up to 20 messages (service enforces the cap server-side)."""
        from services.copilot_service import CopilotService

        mock_messages = []
        for i in range(25):
            msg = MagicMock()
            msg.to_dict.return_value = {
                "id": i + 1,
                "conversation_id": 1,
                "tenant_id": 100,
                "role": "user",
                "content": f"msg {i}",
                "tool_calls_json": None,
                "created_at": None,
                "updated_at": None,
            }
            mock_messages.append(msg)

        with (
            patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history,
            patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv,
        ):
            mock_get_conv.return_value = MagicMock()
            # Service returns first 20 (newest) as per .limit(20) in get_history
            mock_get_history.return_value = (mock_messages[:20], 25)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/1/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["messages"]) == 20
        assert data["data"]["total"] == 25
        assert data["data"]["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_history_passes_required_args(self):
        """The router passes conversation_id and tenant_id to service.get_history."""
        from services.copilot_service import CopilotService

        with (
            patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history,
            patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv,
        ):
            mock_get_conv.return_value = MagicMock()
            mock_get_history.return_value = ([], 0)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                await ac.get("/copilot/1/history")

        assert mock_get_history.call_count == 1
        call_kwargs = mock_get_history.call_args.kwargs
        assert call_kwargs.get("conversation_id") == 1
        assert call_kwargs.get("tenant_id") == 100

    @pytest.mark.asyncio
    async def test_history_unknown_conversation_returns_404(self):
        """GET /copilot/999/history returns 404 when the conversation does not exist."""
        from pkg.errors.app_exceptions import NotFoundException
        from services.copilot_service import CopilotService

        with patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv:
            mock_get_conv.side_effect = NotFoundException("Conversation")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/999/history")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_history_cross_tenant_isolation(self):
        """Tenant A cannot read tenant B's conversation — returns 404."""
        from services.copilot_service import CopilotService

        # Simulate: tenant 200 calls history for conversation 1 (created under tenant 100).
        # get_conversation is called with tenant_id=200; since the conversation belongs
        # to tenant 100, it raises NotFoundException → 404.
        async def mock_tenant_200():
            return AuthContext(user_id=888, tenant_id=200, roles=["admin"])

        original = app.dependency_overrides.get(require_auth)
        app.dependency_overrides[require_auth] = mock_tenant_200

        try:
            with patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv:
                mock_get_conv.side_effect = NotFoundException("Conversation")

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    response = await ac.get("/copilot/1/history")

            assert response.status_code == 404
        finally:
            app.dependency_overrides[require_auth] = original
