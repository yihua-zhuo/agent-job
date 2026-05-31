"""Unit tests for src/api/routers/agent_tasks.py — /agents/tasks endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.agent_tasks import agent_tasks_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException
from tests.unit.conftest import make_mock_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


# ---------------------------------------------------------------------------
# Mock task object with to_dict()
# ---------------------------------------------------------------------------


class MockAgentTask:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)
        self.status = getattr(self, "status", "pending")

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "task_id": getattr(self, "task_id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "description": getattr(self, "description", ""),
            "status": self.status,
            "subtasks": getattr(self, "subtasks", []),
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }


AGENT_TASK_ROW = {
    "id": 1,
    "task_id": "atask_abc123def456",
    "tenant_id": 1,
    "description": "Test Agent Task",
    "status": "pending",
    "subtasks": [],
    "created_at": None,
    "updated_at": None,
}


# ---------------------------------------------------------------------------
# Test fixture — factory so each test gets fresh mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_service(monkeypatch):
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    def _make_client():
        mock_service = MagicMock()
        for attr in ("create_task", "list_tasks", "get_task"):
            setattr(mock_service, attr, AsyncMock())

        def agent_task_service_factory(session):
            return mock_service

        monkeypatch.setattr(
            "api.routers.agent_tasks.AgentTaskService",
            agent_task_service_factory,
        )

        app = FastAPI()
        app.include_router(agent_tasks_router)
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()

        async def override_db():
            yield make_mock_session()

        app.dependency_overrides[get_db] = override_db

        @app.exception_handler(AppException)
        async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "message": exc.detail, "code": exc.code},
            )

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test", follow_redirects=True), mock_service

    return _make_client


# ---------------------------------------------------------------------------
# POST /agents/tasks — create agent task
# ---------------------------------------------------------------------------


class TestCreateAgentTaskEndpoint:
    async def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service()
        mock_task = MockAgentTask(AGENT_TASK_ROW)
        svc.create_task = AsyncMock(return_value=mock_task)
        resp = await client.post("/agents/tasks", json={"description": "Test Agent Task"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["description"] == "Test Agent Task"
        assert body["data"]["status"] == "pending"
        assert body["data"]["task_id"] == "atask_abc123def456"

    async def test_empty_description_returns_422(self, client_with_service):
        # Pydantic min_length=1 rejects empty string before it reaches the service
        client, _ = client_with_service()
        resp = await client.post("/agents/tasks", json={"description": ""})
        assert resp.status_code == 422

    async def test_whitespace_description_returns_422(self, client_with_service):
        from pkg.errors.app_exceptions import ValidationException

        client, svc = client_with_service()
        svc.create_task = AsyncMock(side_effect=ValidationException("description cannot be empty"))
        resp = await client.post("/agents/tasks", json={"description": "   "})
        assert resp.status_code == 422

    async def test_service_validation_error_returns_422(self, client_with_service):
        from pkg.errors.app_exceptions import ValidationException

        client, svc = client_with_service()
        svc.create_task = AsyncMock(side_effect=ValidationException("description cannot be empty"))
        resp = await client.post("/agents/tasks", json={"description": "valid"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /agents/tasks — list agent tasks
# ---------------------------------------------------------------------------


class TestListAgentTasksEndpoint:
    async def test_success_no_filters(self, client_with_service):
        client, svc = client_with_service()
        mock_task = MockAgentTask(AGENT_TASK_ROW)
        svc.list_tasks = AsyncMock(return_value=([mock_task], 1))
        resp = await client.get("/agents/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]
        assert "has_next" in body["data"]
        assert "page" in body["data"]
        assert "page_size" in body["data"]

    async def test_filter_by_status(self, client_with_service):
        client, svc = client_with_service()
        svc.list_tasks = AsyncMock(return_value=([], 0))
        resp = await client.get("/agents/tasks?status=pending")
        assert resp.status_code == 200
        svc.list_tasks.assert_awaited()
        call_kwargs = svc.list_tasks.call_args.kwargs
        assert call_kwargs["status"] == "pending"
        assert call_kwargs["tenant_id"] == 1

    async def test_filter_by_date_range(self, client_with_service):
        client, svc = client_with_service()
        svc.list_tasks = AsyncMock(return_value=([], 0))
        resp = await client.get("/agents/tasks?date_from=2026-01-01&date_to=2026-05-31")
        assert resp.status_code == 200
        call_kwargs = svc.list_tasks.call_args.kwargs
        assert call_kwargs["date_from"] is not None
        assert call_kwargs["date_to"] is not None

    async def test_pagination(self, client_with_service):
        client, svc = client_with_service()
        svc.list_tasks = AsyncMock(return_value=([], 0))
        resp = await client.get("/agents/tasks?page=2&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10

    async def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service()
        resp = await client.get("/agents/tasks?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /agents/tasks/{task_id} — get agent task
# ---------------------------------------------------------------------------


class TestGetAgentTaskEndpoint:
    async def test_success(self, client_with_service):
        client, svc = client_with_service()
        mock_task = MockAgentTask(AGENT_TASK_ROW)
        svc.get_task = AsyncMock(return_value=mock_task)
        resp = await client.get("/agents/tasks/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == 1

    async def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service()
        svc.get_task = AsyncMock(side_effect=NotFoundException("AgentTask"))
        resp = await client.get("/agents/tasks/9999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
