# Implementation Plan — Issue #681

## Goal
Create a new `opportunity_activity` ORM model and corresponding Alembic migration to store activity events linked to CRM opportunities. The model stores `tenant_id` (indexed), `opportunity_id` (FK to `opportunities.id` with cascade delete), `event_type` (string), `event_timestamp` (DateTime), and `metadata` (JSONB). The migration adds the table with proper indexes and is reversible.

## Affected Files
- `src/db/models/opportunity_activity.py` — new file: ORM model class
- `alembic/versions/<revision>_create_opportunity_activities.py` — new file: Alembic migration

Note: `src/db/models/__init__.py` and `alembic/env.py` require **no changes** — `__init__.py` auto-discovers modules via `pkgutil.iter_modules`, and `alembic/env.py` imports `db.models` purely for side-effect registration with `Base.metadata`.

## Implementation Steps
1. Read `src/db/models/opportunity.py` and `src/db/models/workflow.py` as templates for field patterns and imports.
2. Create `src/db/models/opportunity_activity.py`:
   - Imports: `DeclarativeBase` from `db.base`, `AsyncGenerator` from `sqlalchemy.orm`, `Integer/String/DateTime/ForeignKey/func` from `sqlalchemy`, `JSONB` from `sqlalchemy.dialects.postgresql`.
   - Class `OpportunityActivityModel` subclassing `Base` with `__tablename__ = "opportunity_activities"`.
   - Fields: `id` (primary key, autoincrement), `tenant_id` (indexed), `opportunity_id` (FK to `opportunities.id`, `ondelete="CASCADE"`, indexed), `event_type` (String 50), `event_timestamp` (DateTime with timezone, no server_default — written explicitly on insert), `metadata` (JSONB, default=dict).
   - `to_dict()` method returning all fields; `event_timestamp` isoformat in dict.
3. Read the most recent alembic revision from `alembic/versions/` to determine `down_revision`.
4. Create the migration file `alembic/versions/<rev>_<desc>.py`:
   - `upgrade()`: `create_table` with all columns, `create_index` on `tenant_id`, `create_index` on `opportunity_id`.
   - `downgrade()`: `drop_index` for both indexes, then `drop_table('opportunity_activities')`.
5. Review the migration for correctness (JSONB dialect, FK constraint with ondelete cascade, proper index names prefixed with `ix_opportunity_activities_`).

## Test Plan
- Unit tests in `tests/unit/`: Create `tests/unit/test_opportunity_activity.py` with a `mock_db_session` fixture using `make_mock_session` and a handler that covers INSERT/SELECT on `opportunity_activities`. Test: model instantiation, `to_dict()` output, `tenant_id` and `opportunity_id` values.
- Integration tests in `tests/integration/`: Create `tests/integration/test_opportunity_activity_integration.py` using fixtures `db_schema`, `tenant_id`, `async_session`. Test: round-trip insert and select, FK cascade delete (deleting the opportunity removes the activity row), index presence via `pg_indexes`.

## Acceptance Criteria
- `src/db/models/opportunity_activity.py` imports cleanly with no type-checking errors.
- Alembic migration applies with `alembic upgrade head` and reverts with `alembic downgrade -1` without errors.
- Second autogenerate (`alembic revision --autogenerate -m "drift_check"`) produces an empty diff (no phantom changes).
- `tenant_id` and `opportunity_id` columns both have indexes in the applied migration.
- `opportunity_id` FK has `ondelete="CASCADE"` so deleting an opportunity removes its activity rows.
- `metadata` column stores and retrieves arbitrary JSON without type errors.
