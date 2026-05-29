Now I have everything needed. Here is the implementation plan:

# Implementation Plan — Issue #524

## Goal

Add a `channel` column (`email`/`sms`/`whatsapp`/`im`) to the `notifications` table via an alembic migration, update `NotificationModel` with a default of `'email'`, and add the field to `NotificationCreate` so it flows through to the service.

## Affected Files

- `alembic/versions/<new_revision>_add_channel_to_notifications.py` — new migration adding the column with server default `'email'`
- `src/db/models/notification.py` — add `channel` attribute to `NotificationModel` with default `'email'`, update `to_dict()`
- `src/api/routers/notifications.py` — add `channel` to `NotificationCreate` schema and pass it in the `send_notification` call
- `src/services/notification_service.py` — accept and forward `channel` in `send_notification()`, defaulting to `'email'` when not provided
- `tests/unit/test_notifications_router.py` — add case for `channel` field serialization in the router test

## Implementation Steps

1. **Spin up a clean `alembic_dev` database** (drop + create), run `alembic upgrade head`, then generate the migration:
   ```
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alemembic_dev;"
   alembic upgrade head
   alembic revision --autogenerate -m "add_channel_to_notifications"
   ```
   In the generated `alembic/versions/<rev>_add_channel_to_notifications.py`, edit `upgrade()` to add the column:
   ```python
   op.add_column("notifications",
       sa.Column("channel", sa.String(length=20), nullable=False, server_default=sa.text("'email'")))
   ```
   And `downgrade()` to drop it:
   ```python
   op.drop_column("notifications", "channel")
   ```
   Verify: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`, then run a second autogenerate to confirm an empty diff; delete the second empty migration if it has `pass` in both bodies.

2. **Update `src/db/models/notification.py`**: add `channel: Mapped[str] = mapped_column(String(20), default='email', nullable=False)` after `related_id`, and add `"channel": self.channel` to `to_dict()`.

3. **Update `src/services/notification_service.py`**: in `send_notification()`, accept `channel: str = 'email'` as an explicit parameter (replacing `**kwargs`), and pass `channel=channel` when constructing `NotificationModel`.

4. **Update `src/api/routers/notifications.py`**: add `channel: str | None = Field(None, max_length=20)` to `NotificationCreate`, and pass `channel=body.channel` in the `svc.send_notification()` call.

5. **Update `tests/unit/test_notifications_router.py`**: in the existing test that posts to `/notifications/send`, add `channel="sms"` to the payload and assert `data["channel"] == "sms"` in the response.

## Test Plan

- **Unit tests in `tests/unit/`**: `test_notifications_router.py` gains one new assertion covering `channel` in the send-response payload.
- **Integration tests in `tests/integration/`**: no new files needed; the existing `db_schema` fixture auto-creates all tables from `Base.metadata`, so `channel` is present automatically when the ORM model is updated.

## Acceptance Criteria

- `alembic upgrade head` applies the new migration without error.
- `alembic downgrade -1` reverts cleanly.
- `NotificationModel` has `channel` attribute defaulting to `'email'`.
- `to_dict()` includes `"channel"` in its returned dict.
- `NotificationCreate` accepts an optional `channel` field.
- `send_notification` service call propagates `channel` through to the ORM object.
- `ruff check src/` and `ruff format --check src/` pass with no errors.
