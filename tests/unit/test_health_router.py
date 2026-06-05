"""Unit tests for src/api/routers/health.py — GET /health/agents endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.health import router
from db.connection import get_db


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def client(mock_db_session):
    """Return a TestClient with get_agent_service fully mocked."""
    mock_agent_service = MagicMock()
    mock_agent_service.get_status = AsyncMock(
        return_value={
            "llm": "ok",
            "agents": ["base", "coordinator"],
            "timestamp": "2026-06-05T00:00:00+00:00",
        }
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db_session

    # Patch the dependency function used by the router
    from api.deps import get_agent_service as _get_agent_service

    app.dependency_overrides[_get_agent_service] = lambda: mock_agent_service

    return TestClient(app, raise_server_exceptions=False), mock_agent_service


class TestHealthAgentsEndpoint:
    def test_health_agents_returns_200(self, client):
        test_client, _ = client
        resp = test_client.get("/health/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["llm"] == "ok"
        assert body["data"]["agents"] == ["base", "coordinator"]
        assert "timestamp" in body["data"]

    def test_health_agents_endpoint_registered(self):
        """The /agents route is registered under the /health prefix."""
        routes = [route.path for route in router.routes]
        assert "/health/agents" in routes
