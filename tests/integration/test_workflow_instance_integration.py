"""Integration tests for WorkflowInstanceModel against a real PostgreSQL DB."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from db.models.workflow_definition import WorkflowDefinitionModel
from db.models.workflow_instance import WorkflowInstanceModel

pytestmark = pytest.mark.integration


async def _seed_definition(async_session, tenant_id: int, name: str = "Test Def", version: str = "1.0") -> int:
    """Create a workflow definition and return its id."""
    defn = WorkflowDefinitionModel(
        tenant_id=tenant_id,
        name=name,
        description="Test description",
        version=version,
        definition_data={"steps": ["step1"]},
    )
    async_session.add(defn)
    await async_session.flush()
    return defn.id


class TestWorkflowInstanceIntegration:
    """Integration tests for WorkflowInstanceModel persistence."""

    async def test_insert_workflow_instance(self, db_schema, tenant_id, async_session):
        """Insert a definition first, then an instance, verify FK linkage."""
        def_id = await _seed_definition(async_session, tenant_id, "Test Def for Instance")
        instance = WorkflowInstanceModel(
            tenant_id=tenant_id,
            definition_id=def_id,
            status="pending",
            context={"init": True},
        )
        async_session.add(instance)
        await async_session.flush()
        assert instance.id is not None
        assert instance.id > 0
        assert instance.definition_id == def_id

    async def test_query_instances_by_tenant(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Multi-tenant isolation: instances belong to the correct tenant."""
        def_id_1 = await _seed_definition(async_session, tenant_id, "Def for Tenant 1")
        def_id_2 = await _seed_definition(async_session, tenant_id_2, "Def for Tenant 2")

        async_session.add(
            WorkflowInstanceModel(
                tenant_id=tenant_id,
                definition_id=def_id_1,
                status="pending",
                context={},
            )
        )
        async_session.add(
            WorkflowInstanceModel(
                tenant_id=tenant_id,
                definition_id=def_id_1,
                status="running",
                context={},
            )
        )
        async_session.add(
            WorkflowInstanceModel(
                tenant_id=tenant_id_2,
                definition_id=def_id_2,
                status="pending",
                context={},
            )
        )
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        # verify both rows belong to tenant_1's definition and have correct statuses
        for row in rows:
            assert row.tenant_id == tenant_id
            assert row.definition_id == def_id_1
        statuses = {row.status for row in rows}
        assert statuses == {"pending", "running"}

        result_t2 = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.tenant_id == tenant_id_2)
        )
        rows_t2 = result_t2.scalars().all()
        assert len(rows_t2) == 1
        # verify the single row belongs to tenant_2's definition
        assert rows_t2[0].tenant_id == tenant_id_2
        assert rows_t2[0].definition_id == def_id_2

    async def test_update_instance_status(self, db_schema, tenant_id, async_session):
        """Change status from 'pending' to 'running', verify the update persists."""
        def_id = await _seed_definition(async_session, tenant_id)
        instance = WorkflowInstanceModel(
            tenant_id=tenant_id,
            definition_id=def_id,
            status="pending",
            context={},
        )
        async_session.add(instance)
        await async_session.flush()
        assert instance.status == "pending"

        instance.status = "running"
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.id == instance.id)
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert updated.status == "running"

    async def test_complete_instance(self, db_schema, tenant_id, async_session):
        """Set completed_at, verify it is not None after flush."""
        def_id = await _seed_definition(async_session, tenant_id)
        now = datetime.now(UTC)
        instance = WorkflowInstanceModel(
            tenant_id=tenant_id,
            definition_id=def_id,
            status="pending",
            context={},
        )
        async_session.add(instance)
        await async_session.flush()

        instance.status = "completed"
        instance.completed_at = now
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.id == instance.id)
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert updated.completed_at is not None

    async def test_cascade_delete_on_definition_delete(self, db_schema, tenant_id, async_session):
        """Insert definition + instance; delete definition; assert instance is gone via FK cascade.

        NOTE: This test assumes the workflow_instances table has an ON DELETE CASCADE FK
        to workflow_definitions. The migration must declare ON DELETE CASCADE on the
        definition_id foreign key for this test to be meaningful.
        """
        def_id = await _seed_definition(async_session, tenant_id)
        instance = WorkflowInstanceModel(
            tenant_id=tenant_id,
            definition_id=def_id,
            status="pending",
            context={},
        )
        async_session.add(instance)
        await async_session.flush()
        instance_id = instance.id

        result_before = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.id == instance_id)
        )
        assert result_before.scalar_one_or_none() is not None

        # Delete the definition — FK cascade should delete the instance
        def_result = await async_session.execute(
            select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.id == def_id)
        )
        definition = def_result.scalar_one_or_none()
        await async_session.delete(definition)
        await async_session.flush()

        result_after = await async_session.execute(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.id == instance_id)
        )
        assert result_after.scalar_one_or_none() is None
