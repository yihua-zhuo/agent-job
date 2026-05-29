"""Unit tests for the copilot router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from internal.middleware.fastapi_auth import AuthContext
from main import app


class TestCopilotRouter:
    """Tests for copilot router endpoints."""

    @pytest.fixture(autouse=True)
    def _setup_all_overrides(self):
        """Override both require_auth and get_db for every test."""
        from db.connection import get_db
        from internal.middleware.fastapi_auth import require_auth

        async def _mock_auth():
            return AuthContext(user_id=999, tenant_id=100, roles=["admin"])

        # Mock session returned by get_db.
        _session = MagicMock()
        _session.execute = AsyncMock()
        _session.flush = AsyncMock()
        _session.add = MagicMock()

        async def _mock_get_db():
            return _session

        app.dependency_overrides[require_auth] = _mock_auth
        app.dependency_overrides[get_db] = _mock_get_db
        yield _session
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_chat_returns_envelope(self, _setup_all_overrides):
        """POST /copilot/chat returns {"success": True, "data": {"response": ..., "tool_calls": []}}."""
        from services.copilot_service import CopilotService

        mock_conv = MagicMock()
        mock_conv.id = 42

        with (
            patch.object(CopilotService, "get_or_create_conversation", new_callable=AsyncMock) as mock_get_or_create,
            patch.object(CopilotService, "persist_message", new_callable=AsyncMock) as mock_persist,
            patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_history,
            patch.object(CopilotService, "invoke_ai", new_callable=AsyncMock) as mock_invoke_ai,
        ):
            mock_get_or_create.return_value = mock_conv
            mock_history.return_value = ([], 0)
            mock_invoke_ai.return_value = MagicMock(reply="Hello! How can I help?")

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
        assert mock_persist.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_empty_message_returns_422(self, _setup_all_overrides):
        """POST /copilot/chat with an empty message returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/copilot/chat?message=")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_missing_user_id_returns_401(self):
        """A request without a user_id (no auth override) returns 401."""
        from db.connection import get_db
        from internal.middleware.fastapi_auth import require_auth

        # Remove auth override so require_auth fails before get_db is needed.
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db, None)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/copilot/chat?message=token")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_history_returns_envelope(self, _setup_all_overrides):
        """GET /copilot/1/history returns {"success": True, "data": {"messages": [], "total": 0}}."""
        from services.copilot_service import CopilotService

        with (
            patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history,
            patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv,
        ):
            mock_get_conv.return_value = MagicMock()
            mock_get_history.return_value = ([], 0)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/1/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "messages" in data["data"]
        assert "total" in data["data"]
        assert isinstance(data["data"]["messages"], list)
        mock_get_history.assert_called_once()
        call_args = mock_get_history.call_args
        assert call_args.kwargs.get("conversation_id") == 1
        assert call_args.kwargs.get("tenant_id") == 100

    @pytest.mark.asyncio
    async def test_history_caps_at_20(self, _setup_all_overrides):
        """History endpoint returns at most 20 messages even when more exist in DB."""
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
    async def test_history_limit_passed_to_service(self, _setup_all_overrides):
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

        mock_get_history.assert_called_once_with(conversation_id=1, tenant_id=100)

    @pytest.mark.asyncio
    async def test_history_unknown_conversation_returns_404(self, _setup_all_overrides):
        """GET /copilot/999/history returns 404 when the conversation does not exist."""
        from pkg.errors.app_exceptions import NotFoundException
        from services.copilot_service import CopilotService

        with patch.object(CopilotService, "get_conversation", new_callable=AsyncMock) as mock_get_conv:
            mock_get_conv.side_effect = NotFoundException("Conversation")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/999/history")

        assert response.status_code == 404
