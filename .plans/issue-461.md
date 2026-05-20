Now I have everything I need. The `WorkflowModel` already exists at `src/db/models/workflow.py` with all requested fields plus a few extras (`description`, `trigger_config`, `created_by`). The `workflows` table was created in migration `b2c3dce4b714`. The model is auto-discovered via `db.models.__init__`. The task is to verify alignment and add tests.

# Implementation Plan — Issue #461

## Goal

Create (verify existence of) `src/db/models/workflow.py` with `WorkflowModel` supporting id, tenant_id, name, trigger_type, conditions JSON, actions JSON, status, created_at, and updated_at. Import it in alembic/env.py. Create a migration capturing any model fields not yet in the DB. Test by running the migration against a local DB and verifying the table exists.

## Affected Files

- `src/db/models/workflow.py` — already exists; verify field definitions match the issue spec and add unit tests
- `alembic/env.py` — already imports `db.models` (the package), which auto-discovers `workflow.py` via `pkgutil.iter_modules` in `db/models/__init__.py`; no changes needed
- `alembic/versions/<new_revision>_add_workflow_model.py` — create via `alembic revision --autogenerate` once the model is confirmed aligned; review and finalize
- `tests/unit/test_workflow_model.py` — add new unit tests for `WorkflowModel` serialization and field behavior

## Implementation Steps

1. **Confirm `src/db/models/workflow.py`** — read the file and verify `WorkflowModel` contains all required fields: `id`, `tenant_id`, `name`, `trigger_type`, `conditions` (JSON/JSONB), `actions` (JSON/JSONB), `status`, `created_at`, `updated_at`. Note any extra fields present (e.g., `description`, `trigger_config`, `created_by`) — these are fine to keep. Ensure the model inherits from `db.base.Base` and uses `Mapped` + `mapped_column` pattern consistent with all other models.

2. **Confirm `alembic/env.py`** — verify it imports `import db.models  # noqa: F401` which auto-discovers all models including `workflow.py`. No changes required.

3. **Spin up a clean local `alembic_dev` DB** (per CLAUDE.md):
   ```
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   export PYTHONPATH=src
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head
   ```

4. **Run autogenerate against alembic_dev**:
   ```
   alembic revision --autogenerate -m "add_workflow_model"
   ```
   Open `alembic/versions/<new_revision>_add_workflow_model.py` and review carefully. Autogenerate produces correct column types for scalar fields but may not correctly infer JSONB — verify that `conditions` and `actions` use `postgresql.JSONB(astext_type=sa.Text())` rather than plain `JSON`. Also verify `server_default=sa.text('now()')` on timestamp columns. Fill in `downgrade()` if autogenerate left it blank.

5. **Verify migration applies cleanly**:
   ```
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

6. **Run a drift check** (second autogen should produce empty diff; delete the revision file if both `upgrade()` and `downgrade()` are `pass`):
   ```
   alembic revision --autogenerate -m "drift_check"
   ```

7. **Add unit tests** in `tests/unit/test_workflow_model.py` — see Test Plan below.

## Test Plan

- **Unit tests in `tests/unit/`**: Create `tests/unit/test_workflow_model.py` covering:
  - `WorkflowModel.to_dict()` returns all expected keys (`id`, `tenant_id`, `name`, `trigger_type`, `conditions`, `actions`, `status`, `created_at`, `updated_at`)
  - `conditions` and `actions` default to `[]` when `None`
  - `status` default is `"draft"`
  - `trigger_type` default is `"manual"`
  - Model uses `JSONB` type for `conditions` and `actions` (via mock session inspection)
  - Use `MockState`, `make_mock_session`, etc. from `tests/unit/conftest.py` — follow existing unit test patterns

- **Integration tests in `tests/integration/`**: Create `tests/integration/test_workflow_model_integration.py` covering:
  - CRUD round-trip: insert a `WorkflowModel`, fetch it back, verify all fields persisted
  - JSON fields (`conditions`, `actions`) round-trip a complex nested structure correctly
  - `tenant_id` filter is enforced (query same row with wrong `tenant_id` returns `None`)
  - Use `db_schema`, `tenant_id`, `async_session` fixtures per CLAUDE.md conventions

## Acceptance Criteria

- `WorkflowModel` exists in `src/db/models/workflow.py` with all fields from the issue spec
- `alembic/env.py` auto-discovers `workflow.py` via the existing `import db.models` pattern — no changes needed
- New migration created with `alembic revision --autogenerate` and reviewed
- Migration applies (`alembic upgrade head`) and rolls back (`alembic downgrade -1`) cleanly
- Drift check produces an empty diff (no unexpected schema drift)
- Unit tests pass: `pytest tests/unit/test_workflow_model.py -v`
- Integration tests pass: `pytest tests/integration/test_workflow_model_integration.py -v`
