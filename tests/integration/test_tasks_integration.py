"""
Web-layer integration tests for /api/v1/tasks — FastAPI router via httpx.

Run with:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_tasks_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# POST /api/v1/tasks — create task
# ---------------------------------------------------------------------------

class TestCreateTask:
    async def test_create_task(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={
                "title": "Review PR #42",
                "description": "Review the new feature PR",
                "priority": "high",
            },
        )
        assert resp.status_code == 201, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Review PR #42"
        assert data["data"]["tenant_id"] == tenant_id_web

    async def test_create_task_minimal_payload(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Minimal task"},
        )
        assert resp.status_code == 201, f"Body: {resp.text}"
        data = resp.json()
        assert data["data"]["title"] == "Minimal task"
        assert data["data"]["description"] == ""

    async def test_create_task_empty_title_rejected(self, api_client: AsyncClient):
        resp = await api_client.post("/api/v1/tasks", json={"title": ""})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tasks — list tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    async def test_list_tasks_empty(self, api_client: AsyncClient):
        resp = await api_client.get("/api/v1/tasks")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]

    async def test_list_tasks_with_data(self, api_client: AsyncClient, tenant_id_web: int):
        # Create 3 tasks
        for i in range(3):
            resp = await api_client.post(
                "/api/v1/tasks",
                json={"title": f"Task {i}"},
            )
            assert resp.status_code == 201, f"Body: {resp.text}"
            assert resp.json()["data"]["tenant_id"] == tenant_id_web
        resp = await api_client.get("/api/v1/tasks")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["data"]["total"] == 3

    async def test_list_tasks_with_status_filter(
        self, api_client: AsyncClient, tenant_id_web: int
    ):
        # Create a pending task
        await api_client.post(
            "/api/v1/tasks",
            json={"title": "Pending Task", "status": "pending"},
        )
        # Create and complete a task
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Completed Task"},
        )
        task_id = create_resp.json()["data"]["id"]
        await api_client.post(f"/api/v1/tasks/{task_id}/complete")

        # Filter by pending status
        resp = await api_client.get("/api/v1/tasks?status=pending")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        # All returned items should have status "pending"
        for item in data["data"]["items"]:
            assert item["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id} — get task
# ---------------------------------------------------------------------------

class TestGetTask:
    async def test_get_task(self, api_client: AsyncClient, tenant_id_web: int):
        # Create a task
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Get Me", "description": "Test description"},
        )
        task_id = create_resp.json()["data"]["id"]
        resp = await api_client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Get Me"
        assert data["data"]["tenant_id"] == tenant_id_web

    async def test_get_task_not_found(self, api_client: AsyncClient):
        resp = await api_client.get("/api/v1/tasks/999999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/tasks/{task_id} — update task
# ---------------------------------------------------------------------------

class TestUpdateTask:
    async def test_update_task_title(self, api_client: AsyncClient):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Original Title"},
        )
        task_id = create_resp.json()["data"]["id"]
        resp = await api_client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Updated Title"

    async def test_update_task_status(self, api_client: AsyncClient):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Status Test", "status": "pending"},
        )
        task_id = create_resp.json()["data"]["id"]
        resp = await api_client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["data"]["status"] == "in_progress"

    async def test_update_task_not_found(self, api_client: AsyncClient):
        resp = await api_client.patch(
            "/api/v1/tasks/999999",
            json={"title": "X"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/tasks/{task_id}/complete — complete task
# ---------------------------------------------------------------------------

class TestCompleteTask:
    async def test_complete_task(self, api_client: AsyncClient):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "To Complete"},
        )
        task_id = create_resp.json()["data"]["id"]
        resp = await api_client.post(f"/api/v1/tasks/{task_id}/complete")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "completed"

    async def test_complete_task_not_found(self, api_client: AsyncClient):
        resp = await api_client.post("/api/v1/tasks/999999/complete")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/tasks/{task_id} — delete task
# ---------------------------------------------------------------------------

class TestDeleteTask:
    async def test_delete_task(self, api_client: AsyncClient):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "To Delete"},
        )
        task_id = create_resp.json()["data"]["id"]
        resp = await api_client.delete(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200, f"Body: {resp.text}"
        assert resp.json()["success"] is True

        # Subsequent GET should return 404
        get_resp = await api_client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 404

    async def test_delete_task_not_found(self, api_client: AsyncClient):
        resp = await api_client.delete("/api/v1/tasks/999999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth — unauthenticated requests return 401
# ---------------------------------------------------------------------------

class TestUnauthenticatedRequests:
    async def test_unauthenticated_create_returns_401(self, client):
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "Should fail"},
        )
        assert resp.status_code == 401, f"Body: {resp.text}"

    async def test_unauthenticated_list_returns_401(self, client):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 401, f"Body: {resp.text}"

    async def test_unauthenticated_get_returns_401(self, client):
        resp = await client.get("/api/v1/tasks/1")
        assert resp.status_code == 401, f"Body: {resp.text}"

    async def test_unauthenticated_update_returns_401(self, client):
        resp = await client.patch("/api/v1/tasks/1", json={"title": "X"})
        assert resp.status_code == 401, f"Body: {resp.text}"

    async def test_unauthenticated_complete_returns_401(self, client):
        resp = await client.post("/api/v1/tasks/1/complete")
        assert resp.status_code == 401, f"Body: {resp.text}"

    async def test_unauthenticated_delete_returns_401(self, client):
        resp = await client.delete("/api/v1/tasks/1")
        assert resp.status_code == 401, f"Body: {resp.text}"
