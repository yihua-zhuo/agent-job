Now I have all the context I need. Let me write the implementation plan.

# Implementation Plan — Issue #495

## Goal
Add two new SQLAlchemy ORM models (`WebhookModel`, `WebhookDeliveryModel`) and an Alembic migration so the CRM can store webhook configurations and delivery records. Both models follow the existing `Mapped[]`-style patterns, include `tenant_id` for multi-tenancy isolation, and are auto-discovered by `alembic/env.py` via the existing `pkgutil`-based `__init__.py` — so no changes are needed to `alembic/env.py` or `src/db/models/__init__.py`.

## Affected Files
- `src/db/models/webhook.py` — **new** — defines `WebhookModel` and `WebhookDeliveryModel` ORM classes
- `alembic/versions/<hash>_add_webhook_tables.py` — **new** — Alembic migration creating `webhooks` and `webhook_deliveries` tables
- `tests/unit/test_webhook_model.py` — **new** — unit tests for `to_dict()`, field defaults, and enum values on both models
- `tests/integration/test_webhook_model_integration.py` — **new** — integration tests creating and querying records against a real PostgreSQL DB

## Implementation Steps
1. Create `src/db/models/webhook.py` with two SQLAlchemy ORM classes:
   - `WebhookModel` with columns: `id` (PK, autoincrement), `tenant_id` (indexed), `url` (String 2000), `events` (JSON list of strings), `secret` (String 255, nullable), `is_active` (Boolean, default True), `created_at` (DateTime, server_default now). Add a composite index `ix_webhooks_tenant_active` on `(tenant_id, is_active)`.
   - `WebhookDeliveryModel` with columns: `id` (PK, autoincrement), `webhook_id` (FK → `webhooks.id`, cascade delete), `tenant_id` (indexed), `event_type` (String 100), `payload` (JSON), `status` (String 20, default "pending"), `response` (JSON, nullable), `attempts` (Integer, default 1), `delivered_at` (DateTime, nullable). Add an index on `webhook_id`.
   - Both models inherit from `db.base.Base`, use `Mapped[]` / `mapped_column()` style, and implement `to_dict()`.
2. Generate the Alembic migration by spinning up a clean `alembic_dev` database, running `alembic upgrade head`, then `alembic revision --autogenerate -m "add webhook tables"`. Review the generated file: set `server_default=sa.text('now()')` for timestamp columns, use `sa.String(length=2000)` for `url`, include the FK constraint with `ondelete='CASCADE'`, and write a complete `downgrade()` that drops the child table first, then the parent. Verify `upgrade head` → `downgrade -1` → `upgrade head` passes cleanly. Delete any empty drift-check revision generated afterwards.
3. Confirm `alembic/env.py` and `src/db/models/__init__.py` need no changes — the `pkgutil` auto-discovery in `__init__.py` already picks up any new model file in the package, and `import db.models` in `alembic/env.py` triggers it.
4. Create `tests/unit/test_webhook_model.py` with test cases: `to_dict()` serialisation for both models (all fields present, datetimes ISO-formatted, JSON fields are lists/dicts), default values (`is_active=True`, `attempts=1`, `status="pending"`), nullable fields (`secret`, `response`), and relationship direction (FK on `WebhookDeliveryModel`). Use the same pattern as existing unit tests — no DB needed.
5. Create `tests/integration/test_webhook_model_integration.py` with a `@pytest.mark.integration` class that uses `db_schema`, `tenant_id`, and `async_session` fixtures. Test: insert a `WebhookModel` row via session, flush, insert a `WebhookDeliveryModel` row referencing it, commit, then query both back and assert field values. Also test that delivery is returned in a query filtered by `tenant_id` and that deleting the parent webhook cascades the delivery row (using `db_schema`-level isolation).

## Test Plan
- Unit tests in `tests/unit/test_webhook_model.py`: instantiate both models directly (no DB), assert `to_dict()` output shape, assert defaults, assert FK relationship exists on `WebhookDeliveryModel.webhook_id`.
- Integration tests in `tests/integration/test_webhook_model_integration.py`: use `async_session` to insert and query real rows — verifies the migration applies correctly and the ORM columns map to actual DB columns.

## Acceptance Criteria
- `src/db/models/webhook.py` defines both `WebhookModel` and `WebhookDeliveryModel` with all specified columns, correct types, and a `to_dict()` method each.
- `alembic/versions/<hash>_add_webhook_tables.py` creates both tables with the correct column types, indexes, and FK constraint, and `downgrade()` drops them in correct order.
- `alembic upgrade head` and `alembic downgrade -1` both succeed on a clean `alembic_dev` database.
- `pytest tests/unit/test_webhook_model.py -v` passes with no DB dependency.
- `pytest tests/integration/test_webhook_model_integration.py -v` passes against a real PostgreSQL DB (requires `DATABASE_URL`).
