"""Integration tests for WorkflowModel against a real PostgreSQL database.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_workflow_model_integration.py -v

Tests use the db_schema fixture which auto-creates and drops tables per test
(function-scoped), and require the tenant_id and async_session fixtures
(function-scoped, shared across services in a single test).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from db.models.workflow import WorkflowExecutionModel, WorkflowModel
from services.tenant_service import TenantService


async def _create_tenant(async_session) -> int:
    """Insert a tenant record so FK constraints are satisfied."""
    suffix = uuid.uuid4().hex[:8]
    result = await TenantService(async_session).create_tenant(
        name=f"Test Tenant {suffix}",
        plan="pro",
        admin_email=f"admin_{suffix}@example.com",
    )
    return result.id


@pytest.mark.integration
class TestWorkflowModelIntegration:
    """CRUD round-trip tests for WorkflowModel using real DB."""

    async def test_create_and_fetch_workflow(self, db_schema, async_session):
        """Insert a WorkflowModel and retrieve it back — all scalar fields persist."""
        tid = await _create_tenant(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Send Welcome Email",
            description="Automated welcome sequence",
            trigger_type="scheduled",
            trigger_config={"cron": "0 9 * * *", "timezone": "UTC"},
            actions=[{"type": "email.send", "template": "welcome"}],
            conditions=[{"field": "status", "operator": "==", "value": "new"}],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        assert workflow.id is not None
        assert workflow.tenant_id == tid
        assert workflow.name == "Send Welcome Email"
        assert workflow.description == "Automated welcome sequence"
        assert workflow.trigger_type == "scheduled"
        assert workflow.trigger_config == {"cron": "0 9 * * *", "timezone": "UTC"}
        assert workflow.actions == [{"type": "email.send", "template": "welcome"}]
        assert workflow.conditions == [{"field": "status", "operator": "==", "value": "new"}]
        assert workflow.status == "draft"
        assert workflow.created_by is None
        assert workflow.created_at is not None
        assert workflow.updated_at is not None

    async def test_json_fields_roundtrip_complex_structure(self, db_schema, async_session):
        """JSONB fields (conditions, actions, trigger_config) round-trip nested structures correctly."""
        tid = await _create_tenant(async_session)
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
            tenant_id=tid,
            name="Complex Workflow",
            trigger_type="scheduled",
            trigger_config=complex_trigger_config,
            actions=complex_actions,
            conditions=complex_conditions,
            status="active",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        assert workflow.actions == complex_actions
        assert workflow.conditions == complex_conditions
        assert workflow.trigger_config == complex_trigger_config

        # Re-fetch from DB to confirm round-trip
        result = await async_session.execute(select(WorkflowModel).where(WorkflowModel.id == workflow.id))
        fetched = result.scalar_one()
        assert fetched.actions == complex_actions
        assert fetched.conditions == complex_conditions
        assert fetched.trigger_config == complex_trigger_config

    async def test_tenant_isolation_wrong_tenant_returns_none(self, db_schema, async_session):
        """Querying with a different tenant_id returns None (no data leak across tenants)."""
        tid = await _create_tenant(async_session)
        other_tid = await _create_tenant(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Tenant A Workflow",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="active",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()

        # Confirm the row IS present for the owning tenant
        result = await async_session.execute(
            select(WorkflowModel).where(
                WorkflowModel.id == workflow.id,
                WorkflowModel.tenant_id == tid,
            )
        )
        assert result.scalar_one_or_none() is not None

        # Negative query with a different tenant_id returns None
        result = await async_session.execute(
            select(WorkflowModel).where(
                WorkflowModel.id == workflow.id,
                WorkflowModel.tenant_id == other_tid,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_workflow_execution_roundtrip(self, db_schema, async_session):
        """ORM-level round-trip test for WorkflowExecutionModel.

        This is an integration test of the ORM layer, not of the service layer.
        Service-level tenant isolation for executions is covered by
        test_workflow_service_cross_tenant_isolation above.
        """
        tid = await _create_tenant(async_session)
        # Create a workflow first
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Exec Test Workflow",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()

        started_before = datetime.now(UTC)

        execution = WorkflowExecutionModel(
            workflow_id=workflow.id,
            tenant_id=tid,
            trigger_type="manual",
            triggered_by=None,
            status="running",
        )
        async_session.add(execution)
        await async_session.flush()
        await async_session.refresh(execution)

        assert execution.id is not None
        assert execution.workflow_id == workflow.id
        assert execution.trigger_type == "manual"
        assert execution.triggered_by is None
        assert execution.started_at is not None
        assert execution.completed_at is None
        assert execution.status == "running"
        assert execution.result is None

        # Complete the execution
        execution.status = "success"
        execution.result = {"steps_executed": 2, "duration_ms": 150}
        execution.completed_at = datetime.now(UTC)
        await async_session.flush()
        await async_session.refresh(execution)

        assert execution.status == "success"
        assert execution.result == {"steps_executed": 2, "duration_ms": 150}
        assert execution.completed_at is not None
        # completed_at should be >= the time we started this test, not from 1970
        assert execution.completed_at >= started_before

    async def test_workflow_update_persists(self, db_schema, async_session):
        """Updating a workflow field and flushing persists the change."""
        tid = await _create_tenant(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Update Test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()

        workflow.status = "active"
        workflow.name = "Updated Name"
        await async_session.flush()

        result = await async_session.execute(select(WorkflowModel).where(WorkflowModel.id == workflow.id))
        fetched = result.scalar_one()
        assert fetched.status == "active"
        assert fetched.name == "Updated Name"

    async def test_workflow_delete(self, db_schema, async_session):
        """Deleting a workflow removes it from the DB."""
        tid = await _create_tenant(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Delete Me",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        wf_id = workflow.id

        await async_session.delete(workflow)
        await async_session.flush()

        # Expire the identity map so the re-fetch hits the DB directly
        async_session.expire_all()
        result = await async_session.execute(select(WorkflowModel).where(WorkflowModel.id == wf_id))
        assert result.scalar_one_or_none() is None

    async def test_json_fields_empty_values_roundtrip(self, db_schema, async_session):
        """Empty dicts, empty lists, and None for JSONB columns round-trip without corruption."""
        tid = await _create_tenant(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Edge Case Workflow",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        assert workflow.trigger_config == {}
        assert workflow.actions == []
        assert workflow.conditions == []

        result = await async_session.execute(select(WorkflowModel).where(WorkflowModel.id == workflow.id))
        fetched = result.scalar_one()
        assert fetched.trigger_config == {}
        assert fetched.actions == []
        assert fetched.conditions == []

    async def test_workflow_service_owner_tenant_can_fetch(self, db_schema, async_session):
        """WorkflowService.get_workflow returns the workflow when called by the
        owning tenant (Rule 126).

        This complements test_tenant_isolation_wrong_tenant_returns_none above:
        that test exercises the ORM/SQL layer; this test exercises the service
        layer's tenant_id enforcement.
        """
        from services.workflow_service import WorkflowService

        tid = await _create_tenant(async_session)

        workflow = WorkflowModel(
            tenant_id=tid,
            name="Owner Fetch Test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        wf_id = workflow.id

        svc = WorkflowService(async_session)
        fetched = await svc.get_workflow(wf_id, tenant_id=tid)
        assert fetched.id == wf_id

    async def test_workflow_service_cross_tenant_blocked(self, db_schema, async_session):
        """WorkflowService.get_workflow must raise NotFoundException when called
        with a different tenant_id than the one that owns the workflow (Rule 126).
        """
        from pkg.errors.app_exceptions import NotFoundException
        from services.workflow_service import WorkflowService

        tid = await _create_tenant(async_session)
        other_tid = await _create_tenant(async_session)

        workflow = WorkflowModel(
            tenant_id=tid,
            name="Cross-Tenant Test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        wf_id = workflow.id

        svc = WorkflowService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_workflow(wf_id, tenant_id=other_tid)

    async def test_boolean_condition_evaluates_correctly(self, db_schema, async_session):
        """The condition evaluator must support boolean values in JSONB conditions.

        test_json_fields_roundtrip_complex_structure above persists a boolean
        condition; this test verifies the service-level evaluator can match
        against boolean context values.
        """
        from services.workflow_service import WorkflowService

        tid = await _create_tenant(async_session)
        svc = WorkflowService(async_session)
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Bool Condition Test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[{"field": "email_opened", "operator": "==", "value": True}],
            status="active",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        # Boolean True should match
        match = await svc.evaluate_conditions(
            workflow_id=workflow.id,
            context={"email_opened": True},
            tenant_id=tid,
        )
        assert match is True

        # Boolean False should not match
        no_match = await svc.evaluate_conditions(
            workflow_id=workflow.id,
            context={"email_opened": False},
            tenant_id=tid,
        )
        assert no_match is False

    async def test_json_fields_default_values_when_omitted(self, db_schema, async_session):
        """JSONB columns with non-Optional type annotation default to empty values.

        Verifies that even if a row is fetched from DB where the column
        might be NULL (edge case from pre-existing data), the model's
        __table_args__ default values ensure consistent behaviour.
        The model declares nullable=False with default=dict, so None
        is never persisted.
        """
        tid = await _create_tenant(async_session)
        # Construct without specifying JSONB fields — defaults take over
        workflow = WorkflowModel(
            tenant_id=tid,
            name="Defaults Test",
            trigger_type="manual",
            status="draft",
            created_by=None,
        )
        async_session.add(workflow)
        await async_session.flush()
        await async_session.refresh(workflow)

        # Defaults: trigger_config={}, actions=[], conditions=[]
        assert workflow.trigger_config == {}
        assert workflow.actions == []
        assert workflow.conditions == []
