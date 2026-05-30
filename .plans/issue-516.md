Now I have everything needed. Here's the implementation plan:

# Implementation Plan — Issue #516

## Goal
Add the `workflow_nodes` ORM model (the third and final piece for issue #73) to the existing `src/db/models/workflow.py` file, which already contains `WorkflowModel` and `WorkflowExecutionModel`. Then generate an Alembic migration creating the `workflow_nodes` table (plus `workflow_executions` — since its table was never actually created), plus a separate migration for the already-implemented `WorkflowModel`. Since `pkgutil`-based auto-discovery in `src/db/models/__init__.py` and `alembic/env.py` already picks up the workflow model file, no import changes are needed in either location.

## Affected Files
- `src/db/models/workflow.py` — Add `WorkflowNodeModel` class alongside the two existing models
- `alembic/versions/<hash>_add_workflow_nodes.py` — New migration file for the `workflow_nodes` table (depends on existing migrations)
- `alembic/versions/<hash2>_add_workflow_executions.py` — New migration file for the `workflow_executions` table (the `WorkflowModel` already exists in models but was never migrated)

## Implementation Steps
1. **Add `WorkflowNodeModel` to `src/db/models/workflow.py`**: Follow the exact same conventions as the existing `WorkflowModel` and `WorkflowExecutionModel` in that file:
   - Table name `workflow_nodes`
   - Fields: `id` (PK, autoincrement), `workflow_id` (FK → `workflows.id`, CASCADE, indexed), `tenant_id` (indexed, nullable=False), `node_type` (String(50), default="action"), `definition_json` (JSONB, default=dict), `input` (JSONB, default=dict), `output` (JSONB, nullable=True), `status` (String(50), default="pending"), `execution_order` (Integer, default=0), `created_at` / `updated_at` (DateTime with `server_default=func.now()`)
   - `to_dict()` method matching the existing pattern in the file
   - `ondelete="CASCADE"` on the `workflow_id` FK

2. **Add `WorkflowExecutionModel` missing fields**: Inspect whether `WorkflowExecutionModel` in the file is complete for the table needs. If `trigger_type` or `triggered_by` need `tenant_id`, add it (otherwise executions are tenant-scoped via workflow). Note: `WorkflowExecutionModel` currently has no `tenant_id` — if the query pattern requires tenant isolation on executions, add it.

3. **Spin up a clean `alembic_dev` database** (per CLAUDE.md):
   ```bash
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   export PYTHONPATH=src
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head
   ```

4. **Generate the `workflow_nodes` migration**: Run `alembic revision --autogenerate -m "add_workflow_nodes"` — the `workflow.py` model is already in `Base.metadata` via the auto-import loop in `db/models/__init__.py`, so autogen will detect it.

5. **Review the generated migration**: Autogen never gets enum types, defaults, or index names 100% right. Verify:
   - `workflow_nodes.workflow_id` has a FK pointing to `workflows.id` with `ondelete="CASCADE"`
   - `tenant_id` is indexed with `op.f('ix_workflow_nodes_tenant_id')`
   - Composite index on `tenant_id, workflow_id` or `tenant_id, execution_order` is present
   - All JSONB columns use `server_default=sa.text('now()')` — adjust if needed

6. **Generate a second empty migration to detect drift**: Run `alembic revision --autogenerate -m "drift_check"` — if it produces a migration with only `pass` in both up/down, delete it. If not, step 5 was incomplete.

7. **Verify the migration chain applies and rolls back cleanly**:
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

## Test Plan
- Unit tests in `tests/unit/`: No new test files needed for this schema-only task
- Integration tests in `tests/integration/`: No new test files needed for this schema-only task

## Acceptance Criteria
- `WorkflowNodeModel` is defined in `src/db/models/workflow.py` with all specified fields and a `to_dict()` method
- Alembic migration file exists in `alembic/versions/` that creates the `workflow_nodes` table with correct column types, indexes, and FK constraint
- `alembic upgrade head` succeeds with no errors
- `alembic downgrade -1` reverses the migration cleanly
- Second `alembic revision --autogenerate -m "drift_check"` produces an empty migration (no residual diff)
- `ruff check src/` and `ruff format --check src/` pass on `src/db/models/workflow.py`

## Risks / Open Questions
- Whether `WorkflowExecutionModel` needs a `tenant_id` field for multi-tenant query isolation is unclear from the issue — clarify before generating the migration, since adding it later requires a new migration. Currently it has no `tenant_id`, relying on `workflow_id` FK traversal for tenant scoping.
