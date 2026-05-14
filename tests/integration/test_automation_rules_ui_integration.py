"""
Integration tests for automation rules UI flow — full CRUD cycle via API.

Tests: create, read, update, toggle, delete automation rules.
Tests execution log creation and retrieval.

Run with:
    export DATABASE_URL="postgresql+asyncpg://..."
    PYTHONPATH=src pytest tests/integration/test_automation_rules_ui_integration.py -v
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestAutomationRulesUIIntegration:
    """Full rule CRUD cycle via the automation API endpoints."""

    async def test_create_and_retrieve_rule(self, api_client, tenant_id_web):
        """Create a rule via POST /api/v1/automation/rules and retrieve it."""
        create_payload = {
            "name": "Test Rule",
            "description": "A rule for integration testing",
            "trigger_event": "ticket.created",
            "conditions": [{"field": "priority", "operator": "eq", "value": "high"}],
            "actions": [{"type": "notification.send", "params": {"message": "Alert!"}}],
            "enabled": True,
        }
        response = await api_client.post("/api/v1/automation/rules", json=create_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Test Rule"
        assert data["data"]["trigger_event"] == "ticket.created"
        assert data["data"]["enabled"] is True
        rule_id = data["data"]["id"]

        # Retrieve
        get_resp = await api_client.get(f"/api/v1/automation/rules/{rule_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["success"] is True
        assert get_data["data"]["id"] == rule_id
        assert get_data["data"]["name"] == "Test Rule"
        assert len(get_data["data"]["actions"]) == 1
        assert get_data["data"]["actions"][0]["type"] == "notification.send"

    async def test_list_rules(self, api_client, tenant_id_web):
        """List automation rules returns paginated items."""
        # Seed a rule first
        await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "List Test Rule",
                "trigger_event": "customer.created",
                "conditions": [],
                "actions": [{"type": "task.create", "params": {"title": "Follow up"}}],
                "enabled": True,
            },
        )
        response = await api_client.get("/api/v1/automation/rules")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]
        assert "page_size" in data["data"]
        # At least the seeded rule should appear
        names = [r["name"] for r in data["data"]["items"]]
        assert "List Test Rule" in names

    async def test_update_rule(self, api_client, tenant_id_web):
        """Update an existing rule via PUT /api/v1/automation/rules/{id}."""
        # Create
        create_resp = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Update Me",
                "trigger_event": "opportunity.created",
                "conditions": [],
                "actions": [{"type": "webhook.call", "params": {"url": "http://example.com"}}],
                "enabled": False,
            },
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["data"]["id"]

        # Update
        update_resp = await api_client.put(
            f"/api/v1/automation/rules/{rule_id}",
            json={"name": "Updated Rule Name", "enabled": True},
        )
        assert update_resp.status_code == 200
        update_data = update_resp.json()
        assert update_data["success"] is True
        assert update_data["data"]["name"] == "Updated Rule Name"
        assert update_data["data"]["enabled"] is True

    async def test_toggle_rule(self, api_client, tenant_id_web):
        """Toggle rule enabled/disabled via POST /api/v1/automation/rules/{id}/toggle."""
        # Create a disabled rule
        create_resp = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Toggle Test",
                "trigger_event": "lead.created",
                "conditions": [],
                "actions": [{"type": "tag.add", "params": {"tag": "auto-tagged"}}],
                "enabled": False,
            },
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["data"]["id"]
        assert create_resp.json()["data"]["enabled"] is False

        # Toggle to enabled
        toggle1 = await api_client.post(f"/api/v1/automation/rules/{rule_id}/toggle")
        assert toggle1.status_code == 200
        assert toggle1.json()["data"]["enabled"] is True

        # Toggle back to disabled
        toggle2 = await api_client.post(f"/api/v1/automation/rules/{rule_id}/toggle")
        assert toggle2.status_code == 200
        assert toggle2.json()["data"]["enabled"] is False

    async def test_delete_rule(self, api_client, tenant_id_web):
        """Delete a rule via DELETE /api/v1/automation/rules/{id}."""
        # Create
        create_resp = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Delete Me",
                "trigger_event": "user.login",
                "conditions": [],
                "actions": [{"type": "notification.send", "params": {"message": "logged in"}}],
                "enabled": False,
            },
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["data"]["id"]

        # Delete
        delete_resp = await api_client.delete(f"/api/v1/automation/rules/{rule_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        # Verify gone
        get_resp = await api_client.get(f"/api/v1/automation/rules/{rule_id}")
        assert get_resp.status_code == 404

    async def test_trigger_event_executes_matching_rules(self, api_client, tenant_id_web):
        """POST /api/v1/automation/trigger fires matching rules and returns execution data."""
        # Create a rule that matches customer.created
        await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Trigger Test Rule",
                "trigger_event": "customer.created",
                "conditions": [],
                "actions": [{"type": "notification.send", "params": {"message": "New customer!"}}],
                "enabled": True,
            },
        )

        # Trigger the event
        trigger_resp = await api_client.post(
            "/api/v1/automation/trigger",
            json={
                "event_type": "customer.created",
                "context": {"customer_id": 123, "name": "Test Customer"},
            },
        )
        assert trigger_resp.status_code == 200
        data = trigger_resp.json()
        assert data["success"] is True

    async def test_list_logs(self, api_client, tenant_id_web):
        """GET /api/v1/automation/logs returns paginated execution logs."""
        response = await api_client.get("/api/v1/automation/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]

    async def test_list_logs_filtered_by_rule_id(self, api_client, tenant_id_web):
        """GET /api/v1/automation/logs?rule_id=X filters to that rule only."""
        # Create a rule
        create_resp = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Log Filter Rule",
                "trigger_event": "ticket.updated",
                "conditions": [],
                "actions": [{"type": "notification.send", "params": {"message": "updated"}}],
                "enabled": True,
            },
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["data"]["id"]

        # Filter logs by rule_id
        response = await api_client.get(f"/api/v1/automation/logs?rule_id={rule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Items are filtered to this rule
        for log in data["data"]["items"]:
            assert log["rule_id"] == rule_id

    async def test_list_logs_filtered_by_status(self, api_client, tenant_id_web):
        """GET /api/v1/automation/logs?status=failed returns only failed logs."""
        response = await api_client.get("/api/v1/automation/logs?status=failed")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        for log in data["data"]["items"]:
            assert log["status"] == "failed"

    async def test_404_on_nonexistent_rule(self, api_client, tenant_id_web):
        """GET /api/v1/automation/rules/99999 returns 404."""
        response = await api_client.get("/api/v1/automation/rules/99999")
        assert response.status_code == 404

    async def test_validation_requires_name(self, api_client, tenant_id_web):
        """POST /api/v1/automation/rules without a name returns 422."""
        response = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "trigger_event": "ticket.created",
                "conditions": [],
                "actions": [{"type": "notification.send", "params": {"message": "x"}}],
                "enabled": True,
            },
        )
        assert response.status_code == 422

    async def test_validation_requires_at_least_one_action(self, api_client, tenant_id_web):
        """POST /api/v1/automation/rules with no actions returns 422."""
        response = await api_client.post(
            "/api/v1/automation/rules",
            json={
                "name": "No Actions Rule",
                "trigger_event": "ticket.created",
                "conditions": [],
                "actions": [],
                "enabled": True,
            },
        )
        assert response.status_code == 422

    async def test_pagination_params(self, api_client, tenant_id_web):
        """Pagination parameters page and page_size work."""
        response = await api_client.get("/api/v1/automation/rules?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5
