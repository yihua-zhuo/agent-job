# Implementation Plan — Issue #663

## Goal
Create the `NotificationPreferenceModel` ORM class and an Alembic migration that provisions the `notification_preferences` table with multi-tenant indexes. No service, router, or frontend code is in scope.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0663-add-notificationpreferencemodel-and-migration.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0663-add-notificationpreferencemodel-and-migration.md`

## Affected Files
- `src/db/models/notification_preference.py` — new ORM model class `NotificationPreferenceModel`
- `alembic/versions/<rev>_add_notification_preferences_table.py` — new migration creating the table
- `alembic/env.py` — add explicit import of the new model module so `--autogenerate` sees it
- `tests/unit/test_notification_preference_model.py` — new unit test file

## Implementation Steps

### Step 1: Create `src/db/models/notification_preference.py`

Write the new model file following the established `NotificationModel` convention. Fields: `id`, `user_id`, `tenant_id`, `channel` (`String(50)`), `enabled` (`Boolean`, default `False`), `created_at` (`DateTime(timezone=True)`, `server_default=func.now()`). Include `to_dict()` returning all six keys.

File: `src/db/models/notification_preference.py`

```
PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print(NotificationPreferenceModel.__tablename__)"
→ notification_preferences
```

### Step 2: Register model in `alembic/env.py`

The current `alembic/env.py` only does `import db.models`. While `db/models/__init__.py` uses auto-discovery, explicit import in `alembic/env.py` is the safer pattern (per CLAUDE.md §Alembic Migrations). Add `from db.models.notification_preference import NotificationPreferenceModel` near the existing `import db.models` line.

Verify: `ruff check alembic/env.py` → 0 errors.

### Step 3: Generate Alembic migration

1. `docker compose -f configs/docker-compose.test.yml up -d test-db`
2. `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
3. `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
4. Set `DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"`
5. `alembic upgrade head`
6. `alembic revision --autogenerate -m "add notification_preferences table"`

Review the generated `alembic/versions/<rev>_add_notification_preferences_table.py`:
- `op.create_table('notification_preferences', ...)` is present
- `tenant_id` and `user_id` have `index=True`
- `channel` uses `String(50)` (not unbounded `Text`)
- `enabled` uses `Boolean()` with a server-side default (`text('false')` preferred)
- `created_at` uses `server_default=func.now()` (not a Python callable)
- `downgrade()` calls `op.drop_table('notification_preferences')` — fill in if autogen left it blank

Fix any mismatches manually, then verify `ruff check alembic/versions/<new_rev>.py` → 0 errors.

### Step 4: Run upgrade / downgrade / upgrade cycle on `alembic_dev`

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

All three must exit 0. Then run a drift check: `alembic revision --autogenerate -m "drift_check"` — if the new file has only `pass` in both up/down, delete it.

### Step 5: Create `tests/unit/test_notification_preference_model.py`

Write 4 tests:
- `test_tablename`: asserts `__tablename__ == "notification_preferences"`
- `test_columns_exist`: asserts column names include `id`, `user_id`, `tenant_id`, `channel`, `enabled`, `created_at`
- `test_to_dict_returns_all_fields`: instantiates via `__new__`, sets all fields, asserts `to_dict()` returns correct values including `created_at.isoformat()`
- `test_to_dict_disabled_preference`: sets `enabled=False`, `created_at=None`, asserts `enabled is False` and `created_at is None`

Use the real `NotificationPreferenceModel` import — no DB, no mocking needed for `__new__` + `to_dict()`.

Run: `PYTHONPATH=src pytest tests/unit/test_notification_preference_model.py -v` → `4 passed`

### Step 6: Final lint and format check

```bash
ruff check src/db/models/notification_preference.py alembic/versions/<new_rev>.py tests/unit/test_notification_preference_model.py
ruff format --check src/db/models/notification_preference.py tests/unit/test_notification_preference_model.py
```

All commands must exit 0.

## Test Plan
- Unit tests in `tests/unit/test_notification_preference_model.py`: 4 cases covering `__tablename__`, column existence, `to_dict()` all-fields, `to_dict()` disabled/null edge case. No DB required.
- Dev-plan verification commands per §6 of the board (see below).

**Dev-plan §6 verification commands:**
| Check | Command | Expected |
|---|---|---|
| Model import | `PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print(NotificationPreferenceModel.__tablename__)"` | `notification_preferences` |
| Unit tests | `PYTHONPATH=src pytest tests/unit/test_notification_preference_model.py -v` | `4 passed` |
| Lint (model) | `ruff check src/db/models/notification_preference.py` | 0 errors |
| Lint (migration) | `ruff check alembic/versions/<new_rev>.py` | 0 errors |
| Migration cycle | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | three exit 0s |

## Acceptance Criteria
- `NotificationPreferenceModel` is importable from `db.models` and `__tablename__` is `"notification_preferences"`
- All six columns (`id`, `user_id`, `tenant_id`, `channel`, `enabled`, `created_at`) are declared and appear in `__table__.columns`
- `to_dict()` returns all six keys with correct Python types; `created_at` serializes as ISO string or `None`
- Alembic migration creates `notification_preferences` with `index=True` on `tenant_id` and `user_id`; `downgrade()` drops the table
- `ruff check` passes on all three new/edited files
- `pytest tests/unit/test_notification_preference_model.py -v` → `4 passed`
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0s on `alembic_dev`
