Now I have a complete picture. The models already exist in `src/db/models/automation.py` but need to be split into separate files per the issue, with a migration created. Here is the plan:

---

# Implementation Plan — Issue #684

## Goal

Split the existing combined `automation.py` into dedicated `automation_rule.py` and `automation_log.py` ORM model files and create an Alembic migration to define the `automation_rules` and `automation_logs` tables in PostgreSQL.

## Affected Files
- `src/db/models/automation_rule.py` — **Create** `AutomationRuleModel` (extracted from `automation.py`)
- `src/db/models/automation_log.py` — **Create** `AutomationLogModel` (extracted from `automation.py`)
- `src/db/models/automation.py` — **Delete** (content merged into the two new files above)
- `alembic/versions/<id>_create_automation_tables.py` — **Create** Alembic migration for both tables
- `alembic/env.py` — **No changes needed** (already imports `db.models` package, which auto-discovers all model files via `__init__.py`)
- `tests/unit/test_automation_models.py` — **Create** ORM model unit tests

## Implementation Steps

1. **Read the existing `src/db/models/automation.py`** to extract both model classes, then delete the file.

2. **Create `src/db/models/automation_rule.py`** with `AutomationRuleModel`:
   - Fields: `id` (Integer PK, autoincrement), `tenant_id` (Integer, nullable=False, indexed), `name` (String 255, nullable=False), `trigger_event` (String 100, nullable=False, indexed), `conditions` (JSONB, default=list, nullable=False), `actions` (JSONB, default=list, nullable=False), `enabled` (Boolean, default=True, nullable=False), `created_at` (DateTime timezone=True, server_default=func.now()), `updated_at` (DateTime timezone=True, server_default=func.now(), onupdate=func.now())
   - Include `to_dict()` method serializing all fields, with `.isoformat()` guards on datetime fields
   - Import from `db.base import Base`, `sqlalchemy.orm import Mapped, mapped_column`, `sqlalchemy.dialects.postgresql import JSONB`

3. **Create `src/db/models/automation_log.py`** with `AutomationLogModel`:
   - Fields: `id` (Integer PK, autoincrement), `rule_id` (Integer, FK to `automation_rules.id`, ondelete=CASCADE, nullable=False, indexed), `tenant_id` (Integer, nullable=False, indexed), `trigger_event` (String 100, nullable=False), `trigger_context` (JSONB, default=dict, nullable=False), `actions_executed` (JSONB, default=list, nullable=False), `status` (String 50, default="success", nullable=False), `error_message` (Text, nullable=True), `executed_by` (Integer, default=0, nullable=False), `executed_at` (DateTime timezone=True, server_default=func.now())
   - Include `to_dict()` method serializing all fields, with `.isoformat()` guard on `executed_at`
   - Import `ForeignKey` from `sqlalchemy` in addition to the above

4. **Spin up a clean `alembic_dev` database** and run `alembic upgrade head` to bring it to current head (as documented in CLAUDE.md).

5. **Run `alembic revision --autogenerate -m "create automation_rules and automation_logs"`** against the clean `alembic_dev` database to produce the migration.

6. **Review the generated migration** in `alembic/versions/<id>_create_automation_rules_and_automation_logs.py`: confirm column types match the ORM models (JSONB for JSON columns, Integer FK with CASCADE, DateTime with `server_default=sa.text('now()')`), confirm indexes on `tenant_id` and `rule_id`, confirm the `downgrade()` drops both tables in reverse order.

7. **Verify the migration is clean**: run `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head`. Run a second autogenerate pass (`alembic revision --autogenerate -m "drift_check"`) — if it produces an empty migration (only `pass` in up/down), the migration is complete. Delete the empty drift-check migration.

8. **Add a log-specific handler to `tests/unit/domain_handlers/automation.py`**: extend the existing `make_automation_handler` (or add a new `make_log_handler` function) to handle INSERT/SELECT on `automation_logs` so tests can exercise both models. Follow the same pattern as the existing rule handler — use `MockRow`/`MockResult` and manage `state.automation_logs` dict with auto-incrementing IDs.

## Test Plan
- **Unit tests in `tests/unit/`**: Create `tests/unit/test_automation_models.py` covering:
  - `TestAutomationRuleModel.to_dict()` — serializes all fields including datetime as ISO string
  - `TestAutomationRuleModel.defaults` — `enabled` defaults to `True`, `conditions`/`actions` default to `[]`
  - `TestAutomationLogModel.to_dict()` — serializes all fields including nested JSON and datetime
  - `TestAutomationLogModel.defaults` — `status` defaults to `"success"`, `trigger_context` defaults to `{}`
  - `TestAutomationModels.tenant_id_indexed` — both models have `tenant_id` column marked as indexed
  - Use `MockRow`/`MockResult` directly without needing a full service; construct model instances by passing values through `MockRow` and calling the model's `to_dict()` to verify serialization

## Acceptance Criteria
- `src/db/models/automation_rule.py` and `src/db/models/automation_log.py` exist with valid SQLAlchemy ORM classes extending `Base`
- `src/db/models/automation.py` no longer exists (content relocated)
- `alembic/versions/<id>_create_automation_tables.py` creates both `automation_rules` and `automation_logs` tables with correct columns, indexes, and FK constraint
- `alembic upgrade head` and `alembic downgrade -1` both succeed without error against a live PostgreSQL database
- `tests/unit/test_automation_models.py` runs with `pytest tests/unit/test_automation_models.py -v` and all tests pass
- `ruff check src/db/models/automation_rule.py src/db/models/automation_log.py tests/unit/test_automation_models.py` returns no errors
