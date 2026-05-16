"""
Integration tests for /api/v1/tasks endpoints via httpx.

Run against a real PostgreSQL database:
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
# Task endpoints — /api/v1/tasks
# ---------------------------------------------------------------------------


class TestTaskEndpoints:
    """Full task CRUD and status lifecycle at the web layer."""

    async def test_create_task(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={
                "title": "Integration Test Task",
                "description": "Testing the full API",
                "priority": "high",
                "status": "pending",
            },
        )
        assert resp.status_code == 201, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Integration Test Task"
        assert data["data"]["tenant_id"] == tenant_id_web
        assert data["data"]["status"] == "pending"

    async def test_create_task_with_due_date(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={
                "title": "Task With Due Date",
                "due_date": "2025-12-31",
            },
        )
        assert resp.status_code == 201, f"Body: {resp.text}"
        data = resp.json()
        assert data["data"]["title"] == "Task With Due Date"

    async def test_create_task_validation_empty_title(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "", "description": "Desc"},
        )
        assert resp.status_code == 422

    async def test_create_task_invalid_priority(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Task", "priority": "super-urgent"},
        )
        assert resp.status_code == 422

    async def test_get_task(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Get Test Task", "description": "Desc"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.get(f"/api/v1/tasks/{created_id}")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == created_id
        assert data["data"]["title"] == "Get Test Task"

    async def test_get_task_not_found(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/api/v1/tasks/999999999")
        assert resp.status_code == 404

    async def test_list_tasks(self, api_client: AsyncClient, tenant_id_web: int):
        # Create a few tasks
        for title in ["List Task A", "List Task B"]:
            await api_client.post(
                "/api/v1/tasks",
                json={"title": title, "status": "pending"},
            )

        resp = await api_client.get("/api/v1/tasks")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "has_next" in data["data"]
        assert data["data"]["total"] >= 2
        for item in data["data"]["items"]:
            assert item["tenant_id"] == tenant_id_web, "cross-tenant leak detected"

    async def test_list_tasks_filter_by_status(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/api/v1/tasks?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_list_tasks_pagination(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/api/v1/tasks?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    async def test_list_tasks_page_size_over_100(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/api/v1/tasks?page_size=101")
        assert resp.status_code == 422

    async def test_update_task(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Update Test Task", "priority": "normal"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.patch(
            f"/api/v1/tasks/{created_id}",
            json={"title": "Updated Title", "priority": "high"},
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Updated Title"
        assert data["data"]["priority"] == "high"
        assert data["data"]["tenant_id"] == tenant_id_web

    async def test_update_task_not_found(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.patch(
            "/api/v1/tasks/999999999",
            json={"title": "Updated"},
        )
        assert resp.status_code == 404

    async def test_update_task_partial(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Partial Update Task", "status": "pending"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.patch(
            f"/api/v1/tasks/{created_id}",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "in_progress"

    async def test_complete_task(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Task to Complete", "status": "pending"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.post(f"/api/v1/tasks/{created_id}/complete")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "completed"

    async def test_complete_task_not_found(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post("/api/v1/tasks/999999999/complete")
        assert resp.status_code == 404

    async def test_delete_task(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={"title": "Task to Delete"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.delete(f"/api/v1/tasks/{created_id}")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True

        # Verify it's gone
        get_resp = await api_client.get(f"/api/v1/tasks/{created_id}")
        assert get_resp.status_code == 404

    async def test_delete_task_not_found(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.delete("/api/v1/tasks/999999999")
        assert resp.status_code == 404

    async def test_task_lifecycle(self, api_client: AsyncClient):
        # Create
        create_resp = await api_client.post(
            "/api/v1/tasks",
            json={
                "title": "Full Lifecycle Task",
                "description": "Testing create → get → update → complete → delete",
                "priority": "urgent",
                "status": "pending",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["data"]["id"]

        # Get
        get_resp = await api_client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["title"] == "Full Lifecycle Task"

        # Update
        patch_resp = await api_client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "in_progress"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["status"] == "in_progress"

        # Complete
        complete_resp = await api_client.post(f"/api/v1/tasks/{task_id}/complete")
        assert complete_resp.status_code == 200
        assert complete_resp.json()["data"]["status"] == "completed"

        # Delete
        delete_resp = await api_client.delete(f"/api/v1/tasks/{task_id}")
        assert delete_resp.status_code == 200
