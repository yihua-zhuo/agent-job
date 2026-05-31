# Implementation Plan — Issue #630

## Goal
Add a `ReportDefinition` ORM model for storing report definitions, with multi-tenant fields (`tenant_id`/`owner_tenant_id`), ownership tracking (`created_by`), a JSON `config` column, favorite flag, timestamps, and a typed `report_type` column. Generate an Alembic migration to create the `report_definitions` table as the next revision after `c94d682d4b03_add_ai_conversations`.

## Affected Files
- `src/db/models/report.py` — New file defining `ReportDefinitionModel` class
- `alembic/env.py` — No changes needed; `import db.models` auto-discovers all models via `__init__.py` package enumeration
- `alembic/versions/<new_rev>.py` — New migration file creating the `report_definitions` table (revision after `c94d682d4b03`)

## Implementation Steps
1. Create `src/db/models/report.py` with `ReportDefinitionModel(Base)`, following the pattern from `report_schedule.py` and `automation.py`:
   - `__tablename__ = "report_definitions"`
   - `id: Mapped[int]` — `Integer, primary_key=True, autoincrement=True`
   - `tenant_id: Mapped[int]` — `Integer, nullable=False, index=True` (the tenant that owns this report)
   - `name: Mapped[str]` — `String(255), nullable=False`
   - `report_type: Mapped[str]` — `String(100), nullable=False, index=True` (e.g. `"sales"`, `"marketing"`)
   - `config: Mapped[dict]` — `JSON, default=dict, nullable=False`
   - `owner_tenant_id: Mapped[int]` — `Integer, nullable=False, index=True` (the tenant of the report's owner)
   - `created_by: Mapped[int]` — `Integer, default=0, nullable=False`
   - `is_favorite: Mapped[bool]` — `Boolean, default=False, nullable=False`
   - `created_at: Mapped[datetime]` — `DateTime(timezone=True), server_default=func.now(), nullable=False`
   - `updated_at: Mapped[datetime]` — `DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False`
   - Implement `to_dict()` returning all fields (datetime fields as ISO strings, bools/ints as-is)
2. Run `alembic revision --autogenerate -m "add_report_definitions"` against a clean `alembic_dev` database (see CLAUDE.md for setup steps), targeting the Docker test-db via `DATABASE_URL`.
3. Review the generated `alembic/versions/<rev>_add_report_definitions.py`: confirm the table name, column types, indexes on `tenant_id`, `owner_tenant_id`, and `report_type` are correct; fill in the `downgrade()` if autogenerate left it empty.
4. Verify the migration applies and rolls back cleanly: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`.
5. Run a second empty autogenerate (`alembic revision --autogenerate -m "drift_check"`) and delete it if both up/down are `pass`.

## Test Plan
- Unit tests in `tests/unit/`: Add `tests/unit/test_report.py` (or `tests/unit/test_report_definition.py`) following the existing per-domain test pattern — mock session fixture with `report_handler` if one is added to `conftest.py`, or a no-op handler stub. Cover: model instantiation, `to_dict()` output shape, field defaults.
- Integration tests in `tests/integration/`: Add `tests/integration/test_report_definition_integration.py` using the `db_schema` fixture — insert a row, query it back, verify all columns round-trip correctly.

## Acceptance Criteria
- `from db.models.report import ReportDefinitionModel` imports without error
- `ReportDefinitionModel.__tablename__` equals `"report_definitions"`
- The migration file's `revises` points to `c94d682d4b03`
- `alembic upgrade head` succeeds against the test database with no errors
- `alembic downgrade -1` succeeds and drops the table cleanly
- Unit test `pytest tests/unit/test_report.py -v` passes
- Integration test `pytest tests/integration/test_report_definition_integration.py -v` passes

## Risks / Open Questions
- `owner_tenant_id` is specified in the issue alongside `tenant_id`; clarify whether they can ever differ or if one is always derived from the other — if always identical, the column is redundant and can be omitted.
