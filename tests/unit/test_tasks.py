"""Unit tests for src/api/routers/tasks.py — /api/v1/tasks endpoints."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.tasks import tasks_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import AppException, NotFoundException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


# ---------------------------------------------------------------------------
# Mock task object with to_dict()
# ---------------------------------------------------------------------------

class MockTask:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)
        self.status = "pending" if not hasattr(self, "status") else self.status
        self.priority = "normal" if not hasattr(self, "priority") else self.priority

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "title": getattr(self, "title", None),
            "description": getattr(self, "description", None),
            "assigned_to": getattr(self, "assigned_to", None),
            "due_date": getattr(self, "due_date", None),
            "status": self.status,
            "priority": self.priority,
            "created_by": getattr(self, "created_by", None),
            "completed_at": getattr(self, "completed_at", None),
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }


TASK_ROW = {
    "id": 1,
    "tenant_id": 1,
    "title": "Review PR #42",
    "description": "Review the new feature PR",
    "assigned_to": 99,
    "due_date": None,
    "status": "pending",
    "priority": "high",
    "created_by": 99,
    "completed_at": None,
    "created_at": None,
    "updated_at": None,
}


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.tasks.TaskService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(tasks_router)
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


# ---------------------------------------------------------------------------
# POST /api/v1/tasks — create task
# ---------------------------------------------------------------------------

class TestCreateTaskEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask(TASK_ROW)
        svc.create_task = AsyncMock(return_value=mock_task)
        resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Review PR #42",
                "description": "Review the new feature PR",
                "assigned_to": 99,
                "priority": "high",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["title"] == "Review PR #42"

    def test_minimal_payload_accepted(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask({**TASK_ROW, "title": "Minimal task", "description": ""})
        svc.create_task = AsyncMock(return_value=mock_task)
        resp = client.post("/api/v1/tasks", json={"title": "Minimal task"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["title"] == "Minimal task"

    def test_empty_title_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/tasks", json={"title": ""})
        assert resp.status_code == 422

    def test_service_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.create_task = AsyncMock(side_effect=NotFoundException("任务不存在"))
        resp = client.post("/api/v1/tasks", json={"title": "Task"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tasks — list tasks
# ---------------------------------------------------------------------------

class TestListTasksEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask(TASK_ROW)
        svc.list_tasks = AsyncMock(return_value=[mock_task])
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]

    def test_status_filter(self, client_with_service):
        client, svc = client_with_service
        svc.list_tasks = AsyncMock(return_value=[])
        resp = client.get("/api/v1/tasks?status=pending")
        assert resp.status_code == 200
        svc.list_tasks.assert_called_once()
        call_kwargs = svc.list_tasks.call_args[1]
        assert call_kwargs["status"] == "pending"

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/tasks?page_size=101")
        assert resp.status_code == 422

    def test_page_defaults_to_1(self, client_with_service):
        client, svc = client_with_service
        svc.list_tasks = AsyncMock(return_value=[])
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        call_kwargs = svc.list_tasks.call_args[1]
        assert call_kwargs["page"] == 1
        assert call_kwargs["page_size"] == 20


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id} — get task
# ---------------------------------------------------------------------------

class TestGetTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask(TASK_ROW)
        svc.get_task = AsyncMock(return_value=mock_task)
        resp = client.get("/api/v1/tasks/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_task = AsyncMock(side_effect=NotFoundException("任务不存在"))
        resp = client.get("/api/v1/tasks/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/tasks/{task_id} — update task
# ---------------------------------------------------------------------------

class TestUpdateTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated_row = {**TASK_ROW, "title": "Updated title", "status": "in_progress"}
        mock_task = MockTask(updated_row)
        svc.update_task = AsyncMock(return_value=mock_task)
        resp = client.patch("/api/v1/tasks/1", json={"title": "Updated title"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Updated title"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_task = AsyncMock(side_effect=NotFoundException("任务不存在"))
        resp = client.patch("/api/v1/tasks/9999", json={"title": "X"})
        assert resp.status_code == 404

    def test_empty_title_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.patch("/api/v1/tasks/1", json={"title": ""})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/tasks/{task_id}/complete — complete task
# ---------------------------------------------------------------------------

class TestCompleteTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        completed_row = {**TASK_ROW, "status": "completed", "completed_at": "2026-05-14T12:00:00Z"}
        mock_task = MockTask(completed_row)
        svc.complete_task = AsyncMock(return_value=mock_task)
        resp = client.post("/api/v1/tasks/1/complete")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "completed"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.complete_task = AsyncMock(side_effect=NotFoundException("任务不存在"))
        resp = client.post("/api/v1/tasks/9999/complete")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/tasks/{task_id} — delete task
# ---------------------------------------------------------------------------

class TestDeleteTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_task = AsyncMock(return_value=MockTask(TASK_ROW))
        resp = client.delete("/api/v1/tasks/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "message" in body

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_task = AsyncMock(side_effect=NotFoundException("任务不存在"))
        resp = client.delete("/api/v1/tasks/9999")
        assert resp.status_code == 404
