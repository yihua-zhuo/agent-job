# Implementation Plan — Issue #664

## Goal

Create `NotificationLogModel` ORM class in `src/db/models/notification_log.py` and a corresponding Alembic migration to establish a `notification_logs` table for persisting notification delivery attempt history. The model maps to a multi-tenant table with fields: `id`, `notification_id`, `channel`, `status`, `attempts`, `error`, `created_at`. No service or router layer is included — this is purely a schema + model task scoped to issue #664.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0664-add-notificationlogmodel-and-migration.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0664-add-notificationlogmodel-and-migration.md`

## Affected Files

- `src/db/models/notification_log.py` — **new file** — `NotificationLogModel` ORM class mapped to `notification_logs` table
- `alembic/versions/<new_id>_add_notification_logs.py` — **new file** — Alembic migration creating the table (auto-generated then corrected)
- `src/db/models/__init__.py` — no changes required; `pkgutil.iter_modules` auto-discovers the new model
- `alembic/env.py` — no changes required; `import db.models` already triggers auto-discovery via `globals()` registration
- `tests/unit/test_notification_log_model.py` — **new file** — ORM unit tests for `to_dict()` and field definitions

## Implementation Steps

1. **Create `src/db/models/notification_log.py`**

   - Reference `src/db/models/notification_preference.py` for the exact pattern: `db.base.Base` import, `Mapped`/`mapped_column` annotations, `String(50)`, `Integer`, `Text`, `DateTime(timezone=True)`, `func.now()` as `server_default`.
   - Include `to_dict()` method with `created_at` guarded by `if self.created_at else None`.
   - Fields: `id` (PK, autoincrement), `tenant_id` (index=True), `notification_id` (index=True), `channel` (String 50), `status` (String 50), `attempts` (Integer, default=1), `error` (Text, nullable), `created_at` (DateTime timezone, server_default=func.now, nullable=False).
   - Run `ruff check src/db/models/notification_log.py` — must exit 0.

2. **Start the test database container and prepare `alembic_dev`**

   ```bash
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   ```

3. **Run existing migrations to bring `alembic_dev` to head**
   ```bash
   export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
   export PYTHONPATH=src
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head
   ```

4. **Generate the migration with `alembic revision --autogenerate`**
   ```bash
   alembic revision --autogenerate -m "add_notification_logs"
   ```

5. **Review and correct the generated migration file** (`alembic/versions/<id>_add_notification_logs.py`):
   - Confirm `op.create_table('notification_logs', ...)` is present.
   - Confirm `op.create_index(op.f('ix_notification_logs_tenant_id'), ...)` exists.
   - Confirm `op.create_index(op.f('ix_notification_logs_notification_id'), ...)` exists.
   - Confirm `created_at` uses `server_default=sa.text('now()')` (not bare `nullable=False`).
   - Confirm `sa.DateTime(timezone=True)` for `created_at` (not plain `sa.DateTime`).
   - Confirm `down_revision` points to `c94d682d4b04` (the merge-head after report_definitions and ai_conversations). Do NOT use `c94d682d4b03` — that was the pre-merge tip; `c94d682d4b04` is the correct parent for new migrations on this branch.
   - If autogen omitted `server_default`, add it manually: `server_default=sa.text('now()')` in the column call.

6. **Verify the migration applies and rolls back cleanly**
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```
   All three must exit 0.

7. **Run drift check (second autogen must be empty)**
   ```bash
   alembic revision --autogenerate -m "drift_check"
   ```
   If the new file contains only `pass` in both `upgrade()` and `downgrade()`, delete it. If it shows real diff, investigate and fix Step 6.

8. **Create `tests/unit/test_notification_log_model.py`**
   - Three test methods: `test_to_dict_returns_all_fields`, `test_to_dict_with_error_field`, `test_tablename`.
   - Mirror the style of `tests/unit/test_notification_preference_model.py` exactly.
   - Run `PYTHONPATH=src pytest tests/unit/test_notification_log_model.py -v` — expect `3 passed`.

9. **Final lint check**
   ```bash
   ruff check src/db/models/notification_log.py
   ruff check alembic/versions/<new_id>_add_notification_logs.py
   ```
   Both must exit 0.

10. **Commit and open PR** (per dev-plan §8)
    ```bash
    git add src/db/models/notification_log.py
    git add alembic/versions/<new_id>_add_notification_logs.py
    git add tests/unit/test_notification_log_model.py
    git commit -m "feat(campaigns): add NotificationLogModel and migration for #664"
    git push -u origin "$(git branch --show-current)"
    gh pr create --base master --title "feat(campaigns): add NotificationLogModel and migration (#664)" --body "Closes #664"
    ```

## Test Plan

- **Unit tests** in `tests/unit/test_notification_log_model.py`:
  - `test_to_dict_returns_all_fields` — constructs a model instance with all non-null fields, asserts `to_dict()` contains every key
  - `test_to_dict_with_error_field` — constructs with a non-null `error` string, asserts it is present in dict output
  - `test_table_name` — asserts `NotificationLogModel.__tablename__ == "notification_logs"`
- **Integration test**: none for this issue (model-only, no service/router layer). Deferred to #646 (service layer). Rule 144 gap acknowledged and tracked.
- **Dev-plan §6 verification commands**:
  - `ruff check src/db/models/notification_log.py` → 0 errors
  - `ruff check alembic/versions/<new_id>_add_notification_logs.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_notification_log_model.py -v` → 3 passed
  - `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
  - `alembic revision --autogenerate -m "drift_check"` → empty migration (only `pass` in both up/down)

## Acceptance Criteria

- `src/db/models/notification_log.py` exists with `NotificationLogModel` class inheriting from `Base`, containing fields `id`, `tenant_id`, `notification_id`, `channel`, `status`, `attempts`, `error`, `created_at`, and a `to_dict()` method
- `alembic/versions/<id>_add_notification_logs.py` creates `notification_logs` table with `tenant_id` and `notification_id` indexes, and `server_default=sa.text('now()')` on `created_at`
- `ruff check` passes for the new model file and the new migration file
- `pytest tests/unit/test_notification_log_model.py -v` → `3 passed`
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all exit 0
- Second autogen (`drift_check`) produces an empty migration — no residual drift
- `pkgutil.iter_modules` auto-discovers `NotificationLogModel` — no `__init__.py` or `alembic/env.py` edits required

## Risks / Open Questions

- The dev-plan §2.2 notes `pkgutil.iter_modules` auto-discovers models; `alembic/env.py` imports `db.models` and does not list models explicitly, so no change is needed there. If auto-discovery silently fails, the migration would produce an empty diff — mitigated by the §6 drift-check step.
- Alembic autogen commonly omits `server_default=sa.text('now()')` for `created_at` and may generate plain `sa.DateTime()` instead of `sa.DateTime(timezone=True)` — both require manual correction before the migration is accepted.
