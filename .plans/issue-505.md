# Implementation Plan — Issue #505

## Goal

Create SQLAlchemy ORM models for `Conversation` and `ConversationMessage` in `src/db/models/` and a corresponding Alembic migration, following the existing patterns used throughout the codebase (Mapped columns, `to_dict()`, server-default timestamps, multi-tenant indexes).

## Affected Files

- `src/db/models/conversation.py` — new file: `ConversationModel` ORM class
- `src/db/models/conversation_message.py` — new file: `ConversationMessageModel` ORM class
- `alembic/versions/<timestamp>_add_conversations_and_messages.py` — new file: forward/backward migration

No changes to `alembic/env.py` are required — it already contains `import db.models` which uses `pkgutil` to dynamically discover and import all modules under `src/db/models/`, so the new model files are picked up automatically.

## Implementation Steps

1. **Create `src/db/models/conversation.py`**
   - Follow the `ActivityModel` / `TicketModel` pattern: import from `db.base`, use `Mapped`, `mapped_column`, `DateTime(timezone=True)` with `server_default=func.now()`.
   - Fields: `id` (Integer PK, autoincrement), `tenant_id` (Integer, nullable=False, index=True), `user_id` (Integer, nullable=False, index=True), `channel` (String(50), nullable=False), `created_at` (DateTime, server_default=func.now(), nullable=False).
   - Composite index on `(tenant_id, user_id)`.
   - Add `to_dict()` method mirroring other models (isoformat for `created_at`).

2. **Create `src/db/models/conversation_message.py`**
   - Same pattern as above.
   - Fields: `id` (Integer PK, autoincrement), `conversation_id` (Integer, nullable=False, FK to conversations.id with `ondelete='CASCADE'`), `role` (String(20), nullable=False), `content` (Text, nullable=False), `tool_calls_json` (Text, nullable=True — stores JSON string), `created_at` (DateTime, server_default=func.now(), nullable=False).
   - Index on `conversation_id` and composite index on `(tenant_id, conversation_id)` — add a `tenant_id` column so messages are always scoped to a tenant (consistent with multi-tenancy rules used by every other model; if `tenant_id` is omitted, a join to conversations is needed for every query).
   - Add `to_dict()` method.

3. **Generate the Alembic migration**
   - Get the current head revision: `alembic current` → expected: `c94d682d4b03` (the latest migration `add_ai_conversations`).
   - Run `alembic revision --autogenerate -m "add_conversations_and_messages"` with `PYTHONPATH=src` and a disposable `alembic_dev` database.
   - Review the generated `alembic/versions/<timestamp>_add_conversations_and_messages.py`: verify the `down_revision` points to `c94d682d4b03`, both `upgrade()` and `downgrade()` have real bodies (not just `pass`), and the FK chain is correct.
   - Verify: `alembic upgrade head` → success, `alembic downgrade -1` → success, then a second `alembic revision --autogenerate -m "drift_check"` produces an empty migration (confirm no residual drift). Delete the drift-check migration.

## Test Plan

- No unit tests are required in this task — services and routers for these tables are out of scope (per issue: "No other files should change").
- Integration test file `tests/integration/test_conversation_models_integration.py` (optional, not required by acceptance criteria): verify the tables can be created and queried via the real ORM with a real DB connection — `db_schema` fixture creates all tables via `Base.metadata.create_all`, so this is implicitly covered by existing integration tests already.

## Acceptance Criteria

- `alembic current` reports `c94d682d4b03` before the new migration and the new revision after `alembic upgrade head`.
- `alembic upgrade head` exits with code 0 (no errors).
- `alembic downgrade -1` exits with code 0 and the conversation/conversation_messages tables are dropped.
- `alembic upgrade head` succeeds a second time after the downgrade (idempotent up/down).
- The generated migration file contains both `op.create_table('conversations', ...)` and `op.create_table('conversation_messages', ...)` with correct column types, indexes, and a FK from `conversation_id` to `conversations.id`.
- `ruff check src/db/models/conversation.py src/db/models/conversation_message.py` passes with no errors.
- `mypy src/db/models/conversation.py src/db/models/conversation_message.py` passes with no errors.
