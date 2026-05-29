"""Unit tests for the WebSocket router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocketDisconnect

_TEST_SECRET = "test-secret-32-chars-minimum-xx"  # noqa: S105


@pytest.fixture(scope="session", autouse=True)
def set_jwt_secret():
    import os

    os.environ["JWT_SECRET_KEY"] = _TEST_SECRET
    yield
    del os.environ["JWT_SECRET_KEY"]


# -------------------------------------------------------------------------- #
# TestVerifyWsToken — test verify_ws_token() in isolation
# -------------------------------------------------------------------------- #


class TestVerifyWsToken:
    """Tests for verify_ws_token()."""

    @pytest.fixture
    def auth_service(self):
        from src.services.auth_service import AuthService

        return AuthService(MagicMock(), secret_key=_TEST_SECRET)

    def test_valid_token_returns_context(self, auth_service):
        """A valid JWT from query params should return an AuthContext with tenant_id."""
        from src.api.routers.websocket import verify_ws_token

        token = auth_service.generate_token(user_id=42, username="alice", role="admin", tenant_id=1)
        ws = MagicMock()
        ws.query_params.get = MagicMock(return_value=token)
        ws.headers.get = MagicMock(return_value="")

        ctx = verify_ws_token(ws)

        assert ctx is not None
        assert ctx.user_id == 42
        assert ctx.tenant_id == 1
        assert "admin" in ctx.roles

    def test_missing_token_returns_none(self):
        """When neither query param nor header provides a token, return None."""
        from src.api.routers.websocket import verify_ws_token

        ws = MagicMock()
        ws.query_params.get = MagicMock(return_value=None)
        ws.headers.get = MagicMock(return_value="")

        ctx = verify_ws_token(ws)

        assert ctx is None

    def test_invalid_token_returns_none(self):
        """A malformed JWT should return None (not raise)."""
        from src.api.routers.websocket import verify_ws_token

        ws = MagicMock()
        ws.query_params.get = MagicMock(return_value="not.valid.jwt")
        ws.headers.get = MagicMock(return_value="")

        ctx = verify_ws_token(ws)

        assert ctx is None


# -------------------------------------------------------------------------- #
# TestWsChannel — test ws_channel() by directly invoking the async function
# with mock WebSocket objects.  This avoids TestClient ASGI transport quirks
# and gives deterministic, fast unit tests.
# -------------------------------------------------------------------------- #


@pytest.fixture
def patch_connection_manager(monkeypatch):
    """Patch _connection_manager for the current test, auto-restoring after."""
    mock = MagicMock()
    mock.join = AsyncMock()
    mock.leave = AsyncMock()

    import src.api.routers.websocket as ws_module

    original = ws_module._connection_manager
    monkeypatch.setattr(ws_module, "_connection_manager", mock)
    yield mock
    ws_module._connection_manager = original


class TestWsChannel:
    """Tests for ws_channel()."""

    @pytest.fixture
    def auth_service(self):
        from src.services.auth_service import AuthService

        return AuthService(MagicMock(), secret_key=_TEST_SECRET)

    @pytest.fixture
    def valid_token(self, auth_service):
        return auth_service.generate_token(user_id=1, username="alice", role="admin", tenant_id=1)

    async def test_valid_token_accepts_and_joins(self, valid_token, patch_connection_manager):
        """A valid token should cause accept() and ConnectionManager.join()."""
        from src.api.routers.websocket import ws_channel

        ws = AsyncMock()
        ws.query_params.get = MagicMock(return_value=valid_token)
        ws.headers.get = MagicMock(return_value="")
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        await ws_channel(ws, "ticket", "42")

        ws.accept.assert_called_once()
        patch_connection_manager.join.assert_called_once()
        assert patch_connection_manager.join.call_args[0][0] == "1:ticket:42"
        patch_connection_manager.leave.assert_called_once()

    async def test_missing_token_closes_connection(self, patch_connection_manager):
        """Missing token should close with 1008 and not call accept()."""
        from src.api.routers.websocket import ws_channel

        ws = AsyncMock()
        ws.query_params.get = MagicMock(return_value=None)
        ws.headers.get = MagicMock(return_value="")
        ws.accept = AsyncMock()
        ws.close = AsyncMock()

        await ws_channel(ws, "ticket", "99")

        ws.close.assert_called_once_with(code=1008, reason="Unauthorized")
        ws.accept.assert_not_called()
        patch_connection_manager.join.assert_not_called()

    async def test_invalid_token_closes_connection(self, patch_connection_manager):
        """Invalid token should close with 1008 and not call accept()."""
        from src.api.routers.websocket import ws_channel

        ws = AsyncMock()
        ws.query_params.get = MagicMock(return_value="not.valid.jwt")
        ws.headers.get = MagicMock(return_value="")
        ws.accept = AsyncMock()
        ws.close = AsyncMock()

        await ws_channel(ws, "ticket", "99")

        ws.close.assert_called_once_with(code=WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        ws.accept.assert_not_called()
        patch_connection_manager.join.assert_not_called()
