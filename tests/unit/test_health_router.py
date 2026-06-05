"""Unit tests for src/api/routers/health.py — GET /health/agents endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.deps import get_agent_service
from api.routers.health import router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException
from services.agent_service import AgentStatus


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_status(tenant_id: int, llm_status: str = "ok") -> AgentStatus:
    return AgentStatus(
        llm_status=llm_status,
        agents=["base", "coordinator"],
        tenant_id=tenant_id,
        checked_at=datetime(2026, 6, 5, tzinfo=UTC),
    )


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_agent_service():
    """Build a service mock whose get_status reflects the tenant_id from the caller."""
    mock = MagicMock()

    async def _status(tenant_id: int, **_):
        return _make_status(tenant_id)

    mock.get_status = AsyncMock(side_effect=_status)
    return mock


@pytest.fixture
def client(mock_db_session, mock_agent_service):
    """Return a TestClient with get_agent_service fully mocked and auth bypassed."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=1)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error", "code": "INTERNAL_ERROR"},
        )

    return TestClient(app, raise_server_exceptions=False)


class TestHealthAgentsEndpoint:
    def test_health_agents_returns_200(self, client):
        resp = client.get("/health/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["llm"] == "ok"
        assert body["data"]["agents"] == ["base", "coordinator"]
        assert body["data"]["tenant_id"] == 1
        assert "timestamp" in body["data"]
        assert "message" in body
        assert body["message"] == "Agent health retrieved successfully"

    def test_health_agents_returns_200_when_llm_is_down(self, client, mock_agent_service):
        """When get_status reports llm=error, the endpoint still 200s (status is informational)."""
        async def _status(tenant_id: int, **_):
            return _make_status(tenant_id, llm_status="error")

        mock_agent_service.get_status = AsyncMock(side_effect=_status)
        resp = client.get("/health/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["llm"] == "error"

    def test_health_agents_reflects_caller_tenant(self, mock_db_session, mock_agent_service):
        """get_status is called with the tenant_id from the AuthContext."""
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db_session
        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=7)

        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/health/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tenant_id"] == 7

    def test_health_agents_exception_path(self, client, mock_agent_service):
        """Uncaught exceptions from the service return the global error envelope."""
        mock_agent_service.get_status = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.get("/health/agents")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "INTERNAL_ERROR"

    def test_health_agents_endpoint_registered(self):
        """The /agents route is registered under the /health prefix."""
        routes = [route.path for route in router.routes]
        assert "/health/agents" in routes
