"""
Integration tests for /agents/tasks endpoints via httpx.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestAgentTaskEndpoints:
    """Full agent-task CRUD and status lifecycle at the web layer."""

    async def test_create_agent_task(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post(
            "/agents/tasks",
            json={"description": "Integration Test Agent Task"},
        )
        assert resp.status_code == 201, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["description"] == "Integration Test Agent Task"
        assert data["data"]["tenant_id"] == tenant_id_web
        assert data["data"]["status"] == "pending"
        assert data["data"]["task_id"] is not None

    async def test_create_agent_task_empty_description(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.post("/agents/tasks", json={"description": ""})
        assert resp.status_code == 422

    async def test_get_agent_task(self, api_client: AsyncClient, tenant_id_web: int):
        create_resp = await api_client.post(
            "/agents/tasks",
            json={"description": "Get Test Agent Task"},
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.get(f"/agents/tasks/{created_id}")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == created_id
        assert data["data"]["description"] == "Get Test Agent Task"

    async def test_get_agent_task_not_found(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/agents/tasks/999999999")
        assert resp.status_code == 404

    async def test_list_agent_tasks(self, api_client: AsyncClient, tenant_id_web: int):
        # Create a few tasks
        for desc in ["List Agent Task A", "List Agent Task B"]:
            await api_client.post(
                "/agents/tasks",
                json={"description": desc},
            )

        resp = await api_client.get("/agents/tasks")
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "has_next" in data["data"]
        assert data["data"]["total"] >= 2
        for item in data["data"]["items"]:
            assert item["tenant_id"] == tenant_id_web, "cross-tenant leak detected"

    async def test_list_agent_tasks_filter_by_status(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/agents/tasks?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_list_agent_tasks_pagination(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/agents/tasks?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    async def test_list_agent_tasks_page_size_over_100(self, api_client: AsyncClient, tenant_id_web: int):
        resp = await api_client.get("/agents/tasks?page_size=101")
        assert resp.status_code == 422
