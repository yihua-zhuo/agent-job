"""Integration tests for WorkflowDefinitionModel against a real PostgreSQL DB."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from db.models.workflow_definition import WorkflowDefinitionModel

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


class TestWorkflowDefinitionIntegration:
    """Integration tests for WorkflowDefinitionModel persistence."""

    async def test_insert_workflow_definition(self, db_schema, tenant_id, async_session):
        """Insert a record, flush, verify id is assigned."""
        defn = WorkflowDefinitionModel(
            tenant_id=tenant_id,
            name="My Workflow",
            description="A useful workflow",
            version="1.0",
            definition_data={"steps": ["step1", "step2"]},
        )
        async_session.add(defn)
        await async_session.flush()
        assert defn.id is not None
        assert defn.id > 0

    async def test_query_workflow_definition_by_tenant(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Insert definitions for two tenants; query by tenant_id returns only that tenant's rows."""
        def_id_1 = await _seed_definition(async_session, tenant_id, "Def A", "1.0")
        def_id_2 = await _seed_definition(async_session, tenant_id, "Def B", "2.0")
        _ = await _seed_definition(async_session, tenant_id_2, "Def C", "1.0")
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        ids = {r.id for r in rows}
        assert def_id_1 in ids
        assert def_id_2 in ids
        # tenant 2's definition should not be present
        tenant_2_result = await async_session.execute(
            select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.tenant_id == tenant_id_2)
        )
        tenant_2_rows = tenant_2_result.scalars().all()
        assert len(tenant_2_rows) == 1

    async def test_update_workflow_definition(self, db_schema, tenant_id, async_session):
        """Insert a definition, modify a field, flush, verify updated_at changes."""
        defn = WorkflowDefinitionModel(
            tenant_id=tenant_id,
            name="Original Name",
            version="1.0",
            definition_data={},
        )
        async_session.add(defn)
        await async_session.flush()
        original_updated_at = defn.updated_at

        defn.name = "Updated Name"
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.id == defn.id)
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert updated.updated_at >= original_updated_at

    async def test_delete_workflow_definition(self, db_schema, tenant_id, async_session):
        """Insert and delete, assert the record is gone."""
        defn = WorkflowDefinitionModel(
            tenant_id=tenant_id,
            name="To Delete",
            version="1.0",
            definition_data={},
        )
        async_session.add(defn)
        await async_session.flush()
        def_id = defn.id
        await async_session.delete(defn)
        await async_session.flush()

        result = await async_session.execute(
            select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.id == def_id)
        )
        row = result.scalar_one_or_none()
        assert row is None
