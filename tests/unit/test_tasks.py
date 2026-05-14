"""Unit tests for src/api/routers/tasks.py — /api/v1/tasks endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.tasks import tasks_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
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
        self.status = getattr(self, "status", "pending")
        self.priority = getattr(self, "priority", "normal")

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "tenant_id": getattr(self, "tenant_id", None),
            "title": getattr(self, "title", None),
            "description": getattr(self, "description", ""),
            "assigned_to": getattr(self, "assigned_to", 0),
            "due_date": getattr(self, "due_date", None),
            "status": self.status,
            "priority": self.priority,
            "created_by": getattr(self, "created_by", 0),
            "completed_at": getattr(self, "completed_at", None),
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }


TASK_ROW = {
    "id": 1,
    "tenant_id": 1,
    "title": "Test Task",
    "description": "Test description",
    "assigned_to": 1,
    "due_date": None,
    "status": "pending",
    "priority": "normal",
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
                "title": "Test Task",
                "description": "Test description",
                "priority": "normal",
                "status": "pending",
                "assigned_to": 1,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["title"] == "Test Task"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_task = AsyncMock(side_effect=NotFoundException("Task"))
        resp = client.post(
            "/api/v1/tasks",
            json={"title": "Task", "description": "Desc"},
        )
        assert resp.status_code == 404

    def test_empty_title_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/tasks",
            json={"title": "", "description": "Desc"},
        )
        assert resp.status_code == 422

    def test_invalid_priority_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/tasks",
            json={"title": "Task", "priority": "super-high"},
        )
        assert resp.status_code == 422

    def test_invalid_status_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/tasks",
            json={"title": "Task", "status": "invalid"},
        )
        assert resp.status_code == 422

    def test_with_due_date(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask({**TASK_ROW, "due_date": "2025-12-31"})
        svc.create_task = AsyncMock(return_value=mock_task)
        resp = client.post(
            "/api/v1/tasks",
            json={"title": "Task", "due_date": "2025-12-31"},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/tasks — list tasks
# ---------------------------------------------------------------------------


class TestListTasksEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask(TASK_ROW)
        svc.list_tasks = AsyncMock(return_value=[mock_task])
        svc.count_tasks = AsyncMock(return_value=1)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]
        assert "has_next" in body["data"]

    def test_filter_by_status(self, client_with_service):
        client, svc = client_with_service
        svc.list_tasks = AsyncMock(return_value=[])
        svc.count_tasks = AsyncMock(return_value=0)
        resp = client.get("/api/v1/tasks?status=pending")
        assert resp.status_code == 200

    def test_filter_by_assignee(self, client_with_service):
        client, svc = client_with_service
        svc.list_tasks = AsyncMock(return_value=[])
        svc.count_tasks = AsyncMock(return_value=0)
        resp = client.get("/api/v1/tasks?assigned_to=5")
        assert resp.status_code == 200

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/tasks?page_size=101")
        assert resp.status_code == 422


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
        svc.get_task = AsyncMock(side_effect=NotFoundException("Task"))
        resp = client.get("/api/v1/tasks/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/tasks/{task_id} — update task
# ---------------------------------------------------------------------------


class TestUpdateTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated_row = {**TASK_ROW, "title": "Updated Task"}
        mock_task = MockTask(updated_row)
        svc.update_task = AsyncMock(return_value=mock_task)
        resp = client.patch(
            "/api/v1/tasks/1",
            json={"title": "Updated Task"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Updated Task"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_task = AsyncMock(side_effect=NotFoundException("Task"))
        resp = client.patch("/api/v1/tasks/9999", json={"title": "X"})
        assert resp.status_code == 404

    def test_invalid_priority_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.patch("/api/v1/tasks/1", json={"priority": "bad"})
        assert resp.status_code == 422

    def test_partial_update(self, client_with_service):
        client, svc = client_with_service
        mock_task = MockTask(TASK_ROW)
        svc.update_task = AsyncMock(return_value=mock_task)
        resp = client.patch("/api/v1/tasks/1", json={"status": "completed"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/tasks/{task_id}/complete — complete task
# ---------------------------------------------------------------------------


class TestCompleteTaskEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        completed_row = {**TASK_ROW, "status": "completed"}
        mock_task = MockTask(completed_row)
        svc.complete_task = AsyncMock(return_value=mock_task)
        resp = client.post("/api/v1/tasks/1/complete")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "completed"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.complete_task = AsyncMock(side_effect=NotFoundException("Task"))
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

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_task = AsyncMock(side_effect=NotFoundException("Task"))
        resp = client.delete("/api/v1/tasks/9999")
        assert resp.status_code == 404
