Now I have all the context I need. Let me write the implementation plan.

# Implementation Plan — Issue #145

## Goal
Add a `test_get_unread_count` test method to a new unit test file for `NotificationService`. The test patches `get_unread_count` via `AsyncMock` to verify the method returns the correct unread count before and after marking a notification as read.

## Affected Files
- `tests/unit/test_notification_service.py` — **new file**, contains the `TestNotificationService` class with `test_get_unread_count`
- `tests/unit/domain_handlers/notifications.py` — **new file**, exposes `make_notification_handler(state)` for use in test session fixtures (notification CRUD: INSERT for `send_notification`, SELECT for `mark_as_read`)

## Implementation Steps
1. Create `tests/unit/domain_handlers/notifications.py` with a `make_notification_handler(state)` factory that produces a SQL handler for `send_notification` (INSERT → returns a `MockResult` with an auto-incremented notification ID) and `mark_as_read` (SELECT → returns a `MockRow` or `MockResult` wrapping a notification dict). This follows the same pattern as `make_customer_handler` / `make_count_handler` in the existing domain handlers.
2. In `tests/unit/domain_handlers/notifications.py`, define `get_handlers(state) -> list` that returns `[make_notification_handler(state)]`, and expose it in `__all__`.
3. Create `tests/unit/test_notification_service.py` with an import block mirroring the existing test file style (absolute imports from `src/`), a `mock_db_session` fixture that builds a mock session with the notification handler, and a `TestNotificationService` class containing the single `test_get_unread_count` method using `AsyncMock` patching on `NotificationService` for `get_unread_count` and `mark_as_read`.

## Test Plan
- Unit tests in `tests/unit/`: `test_notification_service.py` — `test_get_unread_count` tests that `get_unread_count(uid, tenant_id=1)` returns 3 after three sends, then 2 after `mark_as_read` is called on the first notification ID
- Integration tests in `tests/integration/`: no changes required

## Acceptance Criteria
- `pytest tests/unit/test_notification_service.py -v -k get_unread_count` — the new test passes
- `pytest tests/unit/test_notification_service.py -q` — the full suite in that file passes
- `grep -E "def test_get_unread_count" tests/unit/test_notification_service.py` — confirms the method exists
- `ruff check tests/unit/` — no lint errors in the test directory
