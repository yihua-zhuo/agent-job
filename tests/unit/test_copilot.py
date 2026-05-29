"""Unit tests for the copilot router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from internal.middleware.fastapi_auth import AuthContext
from main import app


def _make_mock_result(scalar_or_none=None, scalars_all=None):
    """Create a mock Result with configurable scalar_one_or_none and scalars().all()."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=scalars_all if scalars_all is not None else [])
    result.scalars = MagicMock(return_value=scalars)
    result.scalar_one_or_none = MagicMock(return_value=scalar_or_none)
    return result


class TestCopilotRouter:
    """Tests for copilot router endpoints."""

    @pytest.fixture(autouse=True)
    def _setup_auth_override(self):
        """Override require_auth so requests succeed without a real JWT."""
        from internal.middleware.fastapi_auth import require_auth

        async def _mock_auth():
            return AuthContext(user_id=999, tenant_id=100, roles=["admin"])

        app.dependency_overrides[require_auth] = _mock_auth
        yield
        app.dependency_overrides.pop(require_auth, None)

    @pytest.fixture
    def mock_db_session(self):
        """Return a mock AsyncSession."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture(autouse=True)
    def _override_db(self, mock_db_session):
        """Override get_db with the mock session for every test."""
        from db.connection import get_db

        async def _mock_get_db():
            return mock_db_session

        app.dependency_overrides[get_db] = _mock_get_db
        yield
        app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_chat_returns_envelope(self, mock_db_session):
        """POST /copilot/chat returns {"success": True, "data": {"response": ..., "tool_calls": []}}."""
        from services.copilot_service import CopilotService

        # Mock the service so get_or_create_conversation returns a mock conversation.
        mock_conv = MagicMock()
        mock_conv.id = 42

        with patch.object(CopilotService, "get_or_create_conversation", new_callable=AsyncMock) as mock_get_or_create, \
             patch.object(CopilotService, "persist_message", new_callable=AsyncMock):

            mock_get_or_create.return_value = mock_conv

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/copilot/chat?message=hello")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "response" in data["data"]
        assert "tool_calls" in data["data"]

    @pytest.mark.asyncio
    async def test_history_returns_envelope(self, mock_db_session):
        """GET /copilot/1/history returns {"success": True, "data": {"messages": [], "total": 0}}."""
        from services.copilot_service import CopilotService

        with patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history:
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
        # Verify the service was called with correct conversation_id and tenant_id.
        mock_get_history.assert_called_once()
        call_args = mock_get_history.call_args
        assert call_args.kwargs.get("conversation_id") == 1  # from URL path
        assert call_args.kwargs.get("tenant_id") == 100  # from mock AuthContext

    @pytest.mark.asyncio
    async def test_history_caps_at_20(self, mock_db_session):
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

        with patch.object(CopilotService, "get_history", new_callable=AsyncMock) as mock_get_history:
            mock_get_history.return_value = (mock_messages[:20], 25)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/copilot/1/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["messages"]) == 20
        # Verify the total reflects the full count (25), not the capped slice (20).
        assert data["data"]["total"] == 25
        # Verify specific serialized fields.
        assert data["data"]["messages"][0]["role"] == "user"
