Now I have everything I need. The `WorkflowModel` already exists at `src/db/models/workflow.py` with all requested fields plus a few extras (`description`, `trigger_config`, `created_by`). The `workflows` table was created in migration `b2c3dce4b714`. The model is auto-discovered via `db.models.__init__`. The task is to verify alignment and add tests.

# Implementation Plan — Issue #461

## Goal

Verify the existing `WorkflowModel` at `src/db/models/workflow.py` contains every field the issue requires, and add unit + integration test coverage so the model, its migrations, and tenant isolation are all validated against a real DB.

## Affected Files

- `src/db/models/workflow.py` — already exists; verify field definitions match the issue spec and add unit tests
- `alembic/env.py` — already imports `db.models` (the package), which auto-discovers `workflow.py` via `pkgutil.iter_modules` in `db/models/__init__.py`; no changes needed
- `tests/unit/test_workflow_model.py` — add new unit tests for `WorkflowModel` serialization and field behavior
- `tests/unit/domain_handlers/workflow.py` — not required: the existing unit tests construct `WorkflowModel` instances directly and never execute SQL against a mock session. Following the bare-model test pattern used elsewhere (e.g. `test_tenant_model.py`), no domain handler is needed.
- `alembic/versions/a1c2d3e4f5a7_workflow_composite_index.py` — drift fix: adds the composite index declared in `WorkflowModel.__table_args__` that was missing from the `b2c3dce4b714` table creation.
- `alembic/versions/a1c2d3e4f5a8_workflow_created_by_nullable.py` — drift fix: aligns `workflows.created_by` nullability with the model (`nullable=True`).
- `alembic/versions/b3c4d5e6f708_workflow_executions_fk_cascade.py` — drift fix: recreates `workflow_executions.tenant_id` FK with `ondelete='CASCADE'` to match the model.
- `alembic/versions/c4d5e6f70819_workflow_nodes_tenant_fk_cascade.py` — drift fix: creates the `workflow_nodes.tenant_id` FK (missing entirely from the original table) with `ondelete='CASCADE'` to match the model.

## Implementation Steps

1. **Verify `src/db/models/workflow.py`** — read the file and confirm `WorkflowModel` contains all required fields: `id`, `tenant_id`, `name`, `trigger_type`, `conditions` (JSON/JSONB), `actions` (JSON/JSONB), `status`, `created_at`, `updated_at`. Note any extra fields present (e.g., `description`, `trigger_config`, `created_by`) — these are fine to keep. Ensure the model inherits from `db.base.Base` and uses `Mapped` + `mapped_column` pattern consistent with all other models.

2. **Verify `alembic/env.py`** — confirm it imports `import db.models  # noqa: F401` which auto-discovers all models including `workflow.py`. No changes required.

3. **Apply the four drift-fix migrations in order** (they depend on each other and the merge head). They are committed as part of this PR; no further autogenerate is needed:
   - `a1c2d3e4f5a7` — composite index `ix_workflows_tenant_id_status` (uses CONCURRENTLY, `transaction_per_migration = False`)
   - `a1c2d3e4f5a8` — `workflows.created_by` → `nullable=True`
   - `b3c4d5e6f708` — `workflow_executions.tenant_id` FK → `ondelete='CASCADE'`
   - `c4d5e6f70819` — create `workflow_nodes.tenant_id` FK with `ondelete='CASCADE'`

4. **Verify migrations apply cleanly against a fresh DB**:
   ```bash
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   export PYTHONPATH=src
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head
   ```

5. **Verify round-trip** (upgrade then downgrade then upgrade):
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

6. **Run a drift check** (second autogen should produce empty diff):
   ```bash
   alembic revision --autogenerate -m "drift_check"
   ```
   Open the generated file. If both `upgrade()` and `downgrade()` contain only `pass`, delete it — that proves no schema drift remains. If either function contains real DDL, fix the original migration to cover the missing change and rerun this step. No new migration is expected here; the only valid outcome of the drift check is a `pass`/`pass` file that gets deleted.

7. **Add unit tests** in `tests/unit/test_workflow_model.py` — see Test Plan below.

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_workflow_model.py` covers:
  - `WorkflowModel.to_dict()` returns all expected keys (`id`, `tenant_id`, `name`, `trigger_type`, `conditions`, `actions`, `status`, `created_at`, `updated_at`)
  - `conditions` and `actions` default to `[]` when `None`
  - `status` default is `"draft"`
  - `trigger_type` default is `"manual"`
  - Column-type assertion (`JSONB` for `conditions` and `actions`) is **deferred to the integration test** because unit tests construct the model without a session; the integration test inspects `pg_catalog` for the column type.
  - Tenant isolation: a query constructed without `tenant_id` in the `WHERE` clause returns no rows (mocks preserve the tenant predicate)
  - Follows the bare-model test pattern from `test_tenant_model.py` — no domain handler required.

- **Integration tests in `tests/integration/`**: `tests/integration/test_workflow_model_integration.py` covers:
  - CRUD round-trip: insert a `WorkflowModel`, fetch it back, verify all fields persisted
  - JSON fields (`conditions`, `actions`) round-trip a complex nested structure correctly
  - Column-type assertion: `conditions` and `actions` are stored as `jsonb` in `pg_catalog` (inspected via `async_session.execute` against `information_schema.columns`)
  - `tenant_id` filter is enforced (query same row with wrong `tenant_id` returns `None`)
  - Cross-tenant isolation: rows inserted under tenant A must not be visible to queries scoped to tenant B
  - Use `db_schema`, `tenant_id`, `async_session` fixtures per CLAUDE.md conventions

## Acceptance Criteria

- `WorkflowModel` exists in `src/db/models/workflow.py` with all fields from the issue spec
- `alembic/env.py` auto-discovers `workflow.py` via the existing `import db.models` pattern — no changes needed
- The four drift-fix migrations are applied in order; no new autogenerated migration is expected (the model is already at head)
- All four migrations apply (`alembic upgrade head`) and roll back (`alembic downgrade -1`) cleanly
- Drift check produces an empty diff: open the generated `drift_check` file and confirm both `upgrade()` and `downgrade()` contain only `pass`; then delete it
- Unit tests pass: `pytest tests/unit/test_workflow_model.py -v`
- Integration tests pass: `pytest tests/integration/test_workflow_model_integration.py -v`
