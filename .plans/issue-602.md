Now I have all the information I need. Here's the implementation plan:

# Implementation Plan — Issue #602

## Goal

Create a new `TicketCategorizationModel` SQLAlchemy ORM model and a corresponding Alembic migration to store AI-generated ticket categorization results (type, priority, confidence, reasons, suggested assignee/team, and a human override flag). No endpoint wiring is required; tests validate the model and persistence layer.

## Affected Files

- `src/db/models/ticket_categorization.py` — new ORM model file
- `alembic/versions/<hash>_add_ticket_categorization.py` — new migration file
- `tests/unit/test_ticket_categorization_model.py` — new unit test file
- `tests/integration/test_ticket_categorization_integration.py` — new integration test file

## Implementation Steps

1. **Create `src/db/models/ticket_categorization.py`** with `TicketCategorizationModel` class inheriting from `db.base.Base`:
   - `__tablename__ = "ticket_categorizations"`
   - Columns: `id` (Integer, PK, autoincrement), `tenant_id` (Integer, nullable=False, index=True), `ticket_id` (Integer, nullable=False, FK to tickets.id with ondelete=CASCADE), `category_type` (String(50), nullable=False), `priority` (String(50), nullable=True), `confidence` (Numeric(5,4), nullable=True), `reasons` (JSON, nullable=True), `suggested_assignee_id` (Integer, nullable=True), `suggested_team` (String(100), nullable=True), `human_override` (Boolean, nullable=False, server_default=false), `categorized_at` (DateTime timezone=True, nullable=True), plus `created_at` / `updated_at` with `server_default=func.now()`.
   - Composite index on `(tenant_id, ticket_id)`.
   - `to_dict()` method mirroring `TicketModel` pattern (datetime fields via `.isoformat()`, JSON fields defaulted with `or {}`).

2. **Generate the Alembic migration** using the documented workflow:
   - Spin up the disposable `alembic_dev` database via `configs/docker-compose.test.yml`.
   - Run `alembic upgrade head` to bring it to current head.
   - Run `alembic revision --autogenerate -m "add_ticket_categorization"` with `PYTHONPATH=src` and the `alembic_dev` `DATABASE_URL`.
   - Edit the generated file's `upgrade()` to use `server_default=sa.text('now()')` and `server_default=sa.text('false')` for timestamps and booleans respectively (autogen emits Python defaults; the project convention is SQL-side defaults).
   - Verify: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`.
   - Run a drift-check second autogen — if it produces `pass` in both up/down, delete it.

3. **Verify model registration** — the dynamic `import db.models` in `alembic/env.py` auto-discovers all `Base` subclasses in `src/db/models/`, so adding the new file is sufficient; no manual import needed.

## Test Plan

- Unit tests in `tests/unit/test_ticket_categorization_model.py`: Instantiate `TicketCategorizationModel` objects directly (no DB), test field defaults, nullable/non-nullable enforcement, and `to_dict()` output including JSON null guard and datetime isoformat.
- Integration tests in `tests/integration/test_ticket_categorization_integration.py`: Use `db_schema`, `tenant_id`, `async_session` fixtures; create a `TicketCategorizationModel` record via session, commit, then fetch it back and assert all fields round-trip correctly.

## Acceptance Criteria

- `TicketCategorizationModel` is importable from `src.db.models.ticket_categorization` and is a `Base` subclass.
- The Alembic migration creates `ticket_categorizations` table with all specified columns and indexes, applies cleanly with `alembic upgrade head`, and rolls back with `alembic downgrade -1`.
- Unit test: `to_dict()` returns all fields including `human_override` (bool), `confidence` (Decimal), `reasons` (dict or None), and `categorized_at` (ISO string or None).
- Integration test: a record created with `category_type="billing"`, `confidence=0.95`, `reasons={"keywords": ["invoice"]}`, `human_override=True` can be fetched back with all values intact.

## Risks / Open Questions

- `reasons` JSON column: use `JSON` (PostgreSQL JSON, not JSONB) to match the pattern used in `TenantModel.settings` and `CustomerModel.recycle_history` in the codebase.
- `confidence` numeric range: `Numeric(5,4)` allows values 0.0000–0.9999; confirm this is sufficient for confidence scores expressed as probabilities.
