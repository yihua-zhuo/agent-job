# Implementation Plan — Issue #661

## Goal
Replace the existing `notification.py` ORM model with a new `NotificationModel` matching the issue spec (fields: id, user_id, tenant_id, channel, template, params JSON, status, priority, created_at, delivered_at, read_at), then generate an Alembic migration adding a composite index on (user_id, tenant_id, status) and a PostgreSQL partial index for unread in-app notifications.

## Affected Files
- `src/db/models/notification.py` — Replace the existing model with the new field set and updated `to_dict()`
- `src/services/notification_service.py` — Update field references to match the new model (field renames: type → channel, is_read → read_at check, title/content → template/params)
- `alembic/versions/<new_revision>.py` — New migration (chains from `82ecf4a34e34`) adding composite + partial indexes on `notifications`
- `tests/unit/domain_handlers/notification.py` — Handler for unit-test mock SQL engine; discovered automatically by `conftest.py`'s `_load_domain_handler_modules()` via `pkgutil.iter_modules` over the `tests.unit.domain_handlers` package. The handler module must export `get_handlers(state)` and `__all__` listing all exported symbols.
- `tests/unit/test_notifications_router.py` — Tests already use the new field names (`channel`, `template`, `params`, `status`, `read_at`); no updates required

## Implementation Steps
1. **Replace `src/db/models/notification.py`** — DONE: model already updated with all 11 fields, `to_dict()` serializes `params_` as `"params"`.
   - Fields: `id` (pk), `user_id` (index=True), `tenant_id` (index=True), `channel` (String(50)), `template` (String(255)), `payload_params` (JSON, mapped_column `params_`, using `postgresql.JSON`), `status` (String(50)), `priority` (String(20)), `created_at` (DateTime, `server_default=func.now()`), `delivered_at` (DateTime, nullable), `read_at` (DateTime, nullable).
   - Add `__table_args__` with a composite index: `Index("ix_notifications_user_tenant_status", "user_id", "tenant_id", "status")`.
   - Import `JSON` from `sqlalchemy.dialects.postgresql`.
   - `to_dict()` must serialize `payload_params` (check isinstance for JSON dict) and format all three datetime fields with `.isoformat()`. The dict key should use `'params'` (without trailing underscore) — `{"params": self.payload_params, ...}` — to present a clean API contract while the Python attribute remains `payload_params`.
   - Python attribute is `payload_params` (mapped to DB column `params_`).
   - References to the JSON field use `params_` throughout (DB column name) and `payload_params` (Python ORM attribute name) internally.

2. **Create `tests/unit/domain_handlers/notification.py`** with `NotificationMockSession`, `get_handlers(state)`, `make_notification_handler(state)`, and `ORDER = 2`. Follow the same `ORDER`-sorted module loading pattern used by `sla.py` and `counts.py`.

3. **Update `src/services/notification_service.py`**: Already complete — the service was updated to use the new field names (`channel`, `template`, `params_`, `read_at`, `status`) in place of the legacy names.
   - `send_notification` builds `payload_params` as `{"content": content, "related_type": ..., "related_id": ...}`.
   - `mark_as_read` sets `read_at` + `status` via ORM attributes, then calls `flush()` only (no `refresh()`).

4. **Update `tests/unit/test_notifications_router.py`** — `_MockNotificationModel.to_dict()` at line ~51 now outputs `"params"` (not `"params_"`) to match `NotificationModel.to_dict()`.

5. **Generate the migration** (follow CLAUDE.md exactly): ✅ DONE — the migration at `alembic/versions/e7f6a5b3c12d_add_notification_indexes.py` is fully hand-written (not produced by alembic autogenerate) and chains from base revision `82ecf4a34e34`. It contains the manually written partial index (lines 70-78).

6. **Write data transformation logic in the migration**:
   - In `upgrade()`: add new nullable columns → backfill via SQL UPDATE → drop old columns → add indexes
   - In `downgrade()`: drop indexes → add old columns back → reverse backfill via SQL UPDATE → drop new columns
   - Use SQLAlchemy Core `op.execute()` with `text()` for backfill SQL — all migrations must be fully reversible and idempotent
   - Example backfill in `upgrade()`:
     - `UPDATE notifications SET channel = type WHERE type IS NOT NULL`
     - `UPDATE notifications SET template = title WHERE title IS NOT NULL`
     - `UPDATE notifications SET params_ = jsonb_build_object('content', content, 'related_type', related_type, 'related_id', related_id) WHERE ...`
     - `UPDATE notifications SET status = CASE WHEN is_read THEN 'read' ELSE 'pending' END`
     - `UPDATE notifications SET read_at = created_at WHERE is_read = true`
     - `UPDATE notifications SET priority = 'normal' WHERE priority IS NULL` (new field — defaults to 'normal')
     - `UPDATE notifications SET delivered_at = created_at WHERE delivered_at IS NULL` (new field — set to creation time)
   - Example backfill in `downgrade()` (recreates legacy columns, restores legacy data, drops new columns):
     - Add old columns (type, title, content, is_read, related_type, related_id)
     - `UPDATE notifications SET type = channel WHERE channel IS NOT NULL`
     - `UPDATE notifications SET title = template WHERE template IS NOT NULL`
     - `UPDATE notifications SET content = params_->>'content' WHERE params_ IS NOT NULL`
     - `UPDATE notifications SET related_type = params_->>'related_type' WHERE params_ IS NOT NULL`
     - `UPDATE notifications SET related_id = (params_->>'related_id')::bigint WHERE params_ IS NOT NULL`
     - `UPDATE notifications SET is_read = (status = 'read') WHERE status IS NOT NULL`
     - Drop new columns (channel, template, params_, status, priority, delivered_at, read_at)

## Test Plan
- Unit tests in `tests/unit/test_notifications_router.py`: methods `test_list_notifications_ok`, `test_list_unread_only`, `test_list_pagination_params`, `test_send_ok`, `test_send_validation_error`, `test_mark_read_ok`, `test_mark_read_not_found`, `test_mark_all_read_ok`, `test_delete_notification_ok`, `test_delete_notification_not_found`, `test_cancel_reminder_ok`, `test_cancel_reminder_not_found`, `test_cross_tenant_read_returns_empty_list`.
- Integration tests in `tests/integration/`: No new integration test files required — the existing `notifications` table is already covered by `db_schema` fixture; the new indexes are exercised by the existing notification integration flows (list, send, mark-read) with no new fixtures needed.

## Acceptance Criteria
- `src/db/models/notification.py` contains `NotificationModel` with all eleven fields (`id`, `user_id`, `tenant_id`, `channel`, `template`, `params_`, `status`, `priority`, `created_at`, `delivered_at`, `read_at`) and a `to_dict()` method serializing all fields correctly.
- `NotificationModel.params_` is declared with `JSON` type from `sqlalchemy.dialects.postgresql`.
- `__table_args__` defines `Index("ix_notifications_user_tenant_status", "user_id", "tenant_id", "status")`.
- The Alembic migration in `alembic/versions/` contains `op.create_index` for the composite index and a manually written partial index `ix_notifications_in_app_unread` with `WHERE channel='in_app' AND read_at IS NULL`. The partial index must be written manually, not autogenerated.
- Migration upgrades and downgrades cleanly against a real PostgreSQL instance with `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
- `src/services/notification_service.py` uses the new model fields (`channel`, `template`, `params_`, `status`, `read_at`) throughout. `mark_as_read` calls `flush()` only (no `refresh()`); `mark_all_as_read` returns a plain `{"marked_count": <int>}` dict without calling `refresh()`.
- Ruff linting clean: `PYTHONPATH=src ruff check src/`.

## Risks / Open Questions
- The existing `NotificationService` in `notification_service.py` uses field names (`type`, `is_read`) that differ from the new model. These field references must be updated in the service — if the service is also used by other callers (e.g. API router), those callers' serialization layer may also need updating. The router tests patch `NotificationService` directly, so they are insulated, but any integration test that constructs `NotificationModel` directly will break until updated.
- The partial index `WHERE channel='in_app' AND read_at IS NULL` cannot be produced by autogenerate; it must be written manually in the migration. Pass the predicate as a SQLAlchemy Core boolean expression via the `postgresql_where` parameter of `op.create_index()` (e.g., `postgresql_where=and_(column("channel") == "in_app", column("read_at").is_(None))`), or use `text()` for raw SQL.
- `docker compose -f configs/docker-compose.test.yml` is the correct compose file per CLAUDE.md; confirm it exposes the `test-db` container name as referenced in the steps above before running.
