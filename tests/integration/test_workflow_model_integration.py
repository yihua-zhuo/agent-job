"""Integration tests for WorkflowModel against a real PostgreSQL database.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_workflow_model_integration.py -v

Tests use the db_schema fixture which auto-creates and drops tables per test
(function-scoped), and require the tenant_id and async_session fixtures
(function-scoped, shared across services in a single test).
"""

from __future__ import annotations

import pytest

from db.models.workflow import WorkflowExecutionModel, WorkflowModel


@pytest.mark.integration
class TestWorkflowModelIntegration:
    """CRUD round-trip tests for WorkflowModel using real DB."""

    async def test_create_and_fetch_workflow(self, db_schema, tenant_id, async_session):
        """Insert a WorkflowModel and retrieve it back — all scalar fields persist."""
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Send Welcome Email",
            description="Automated welcome sequence",
            trigger_type="scheduled",
            trigger_config={"cron": "0 9 * * *", "timezone": "UTC"},
            actions=[{"type": "email.send", "template": "welcome"}],
            conditions=[{"field": "status", "operator": "==", "value": "new"}],
            status="draft",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        assert workflow.id is not None
        assert workflow.tenant_id == tenant_id
        assert workflow.name == "Send Welcome Email"
        assert workflow.description == "Automated welcome sequence"
        assert workflow.trigger_type == "scheduled"
        assert workflow.trigger_config == {"cron": "0 9 * * *", "timezone": "UTC"}
        assert workflow.actions == [{"type": "email.send", "template": "welcome"}]
        assert workflow.conditions == [{"field": "status", "operator": "==", "value": "new"}]
        assert workflow.status == "draft"
        assert workflow.created_by == 1
        assert workflow.created_at is not None
        assert workflow.updated_at is not None

    async def test_json_fields_roundtrip_complex_structure(self, db_schema, tenant_id, async_session):
        """JSONB fields (conditions, actions, trigger_config) round-trip nested structures correctly."""
        complex_actions = [
            {"type": "email.send", "template": "onboard", "vars": {"name": "{{customer.name}}"}},
            {"type": "task.create", "title": "Follow up in 3 days", "assign_to": 5},
            {
                "type": "condition",
                "if": {"field": "plan", "operator": "==", "value": "enterprise"},
                "then": [{"type": "tag.add", "tag": "enterprise"}],
            },
        ]
        complex_conditions = [
            {"field": "days_since_signup", "operator": ">=", "value": 7},
            {"field": "email_opened", "operator": "==", "value": True},
            {"field": "tags", "operator": "contains", "value": "qualified"},
        ]
        complex_trigger_config = {
            "cron": "0 9 * * MON-FRI",
            "timezone": "America/New_York",
            "lookback_window": "30d",
        }

        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Complex Workflow",
            trigger_type="scheduled",
            trigger_config=complex_trigger_config,
            actions=complex_actions,
            conditions=complex_conditions,
            status="active",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        assert workflow.actions == complex_actions
        assert workflow.conditions == complex_conditions
        assert workflow.trigger_config == complex_trigger_config

        # Re-fetch from DB to confirm round-trip
        from sqlalchemy import select
        result = await async_session.execute(
            select(WorkflowModel).where(WorkflowModel.id == workflow.id)
        )
        fetched = result.scalar_one()
        assert fetched.actions == complex_actions
        assert fetched.conditions == complex_conditions
        assert fetched.trigger_config == complex_trigger_config

    async def test_tenant_isolation_wrong_tenant_returns_none(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Querying with the wrong tenant_id returns None (no data leak across tenants)."""
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Tenant A Workflow",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="active",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()

        from sqlalchemy import select

        # Confirm the row IS present for the owning tenant
        result = await async_session.execute(
            select(WorkflowModel).where(
                WorkflowModel.id == workflow.id,
                WorkflowModel.tenant_id == tenant_id,
            )
        )
        assert result.scalar_one_or_none() is not None

        # Negative query with wrong tenant_id returns None
        result = await async_session.execute(
            select(WorkflowModel).where(
                WorkflowModel.id == workflow.id,
                WorkflowModel.tenant_id == tenant_id_2,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_workflow_execution_roundtrip(self, db_schema, tenant_id, async_session):
        """WorkflowExecutionModel round-trips correctly with all fields."""
        # Create a workflow first
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Exec Test Workflow",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()

        execution = WorkflowExecutionModel(
            workflow_id=workflow.id,
            trigger_type="manual",
            triggered_by=3,
            status="running",
        )
        async_session.add(execution)
        await async_session.flush()
        await async_session.refresh(execution)

        assert execution.id is not None
        assert execution.workflow_id == workflow.id
        assert execution.trigger_type == "manual"
        assert execution.triggered_by == 3
        assert execution.started_at is not None
        assert execution.completed_at is None
        assert execution.status == "running"
        assert execution.result is None

        # Complete the execution
        from datetime import datetime, timezone
        execution.status = "success"
        execution.result = {"steps_executed": 2, "duration_ms": 150}
        execution.completed_at = datetime.now(timezone.utc)
        await async_session.flush()
        await async_session.refresh(execution)

        assert execution.status == "success"
        assert execution.result == {"steps_executed": 2, "duration_ms": 150}
        assert execution.completed_at is not None

    async def test_workflow_update_persists(self, db_schema, tenant_id, async_session):
        """Updating a workflow field and flushing persists the change."""
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Update Test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()

        workflow.status = "active"
        workflow.name = "Updated Name"
        await async_session.flush()

        from sqlalchemy import select
        result = await async_session.execute(
            select(WorkflowModel).where(WorkflowModel.id == workflow.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == "active"
        assert fetched.name == "Updated Name"

    async def test_workflow_delete(self, db_schema, tenant_id, async_session):
        """Deleting a workflow removes it from the DB."""
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name="Delete Me",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=1,
        )
        async_session.add(workflow)
        await async_session.flush()
        wf_id = workflow.id

        await async_session.delete(workflow)
        await async_session.flush()

        from sqlalchemy import select

        # Expire the identity map so the re-fetch hits the DB directly
        async_session.expire_all()
        result = await async_session.execute(select(WorkflowModel).where(WorkflowModel.id == wf_id))
        assert result.scalar_one_or_none() is None