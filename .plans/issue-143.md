Now I have everything I need. Let me write the implementation plan.

---

# Implementation Plan — Issue #143

## Goal

Add a `tests/unit/test_activity_service.py` unit test suite for `ActivityService` covering all core CRUD operations and pagination, matching the patterns used by existing unit tests in the project.

## Affected Files

- `tests/unit/conftest.py` — add `activities` dict + `activities_next_id` to `MockState`, add `make_activity_handler(state)` factory, register it in `all_handlers()`
- `tests/unit/test_activity_service.py` — **new file** — `mock_db_session` fixture + 6 test cases across 3 classes

## Implementation Steps

1. **Add activity state to `MockState`** (`tests/unit/conftest.py`, line ~159):
   - Add `self.activities: dict[int, dict] = {}` and `self.activities_next_id: int = 1`
   - This mirrors the existing pattern for `customers` and `users`

2. **Add `make_activity_handler(state)` factory** (`tests/unit/conftest.py`, after `campaign_handler`):
   - Handle `insert into activities` — populate `state.activities[aid]` and return `MockRow` with all fields (`id`, `tenant_id`, `customer_id`, `opportunity_id`, `type`, `content`, `created_by`, `created_at`)
   - Handle `from activities where` / `update activities` / `delete from activities` — read from `state.activities` by `id` and `tenant_id`, return `MockResult`
   - Handle `select count` for activities — return `MockResult([[len(state.activities)]])` or fall back to count from `state.activities`
   - Handle `select ... from activities` (list) — return all `MockRow` records from `state.activities` filtered by `tenant_id`
   - Raise on invalid type for `create_activity` via `ValidationException` — the handler does not need to handle this; the service raises it before any SQL runs

3. **Register `make_activity_handler` in `all_handlers()`** (`tests/unit/conftest.py`, `all_handlers` function):
   - Append `make_activity_handler(state)` to the returned list

4. **Create `tests/unit/test_activity_service.py`** with:
   - Import `ActivityService`, `Activity`, `ActivityType` from `src`, plus `NotFoundException` and `ValidationException`
   - `mock_db_session` fixture using `MagicMock` pattern (same as `test_customer_service.py`) so `session.execute` uses `AsyncMock(side_effect=...)`; `session.flush` returns `AsyncMock()`; `session.refresh` is a no-op
   - `activity_service` fixture: `return ActivityService(mock_db_session())`
   - `TestCreateActivity` class with `test_create_activity_returns_api_response` — calls `create_activity(customer_id=1, activity_type="call", content="Test call", created_by=1, tenant_id=1)`, asserts returned `Activity` has `.content == "Test call"` and `.type == ActivityType.CALL`
   - `TestGetActivity` class with `test_get_activity_found` — first creates an activity via the service (use `session.flush` side-effect to populate a row the subsequent GET can find), then calls `get_activity(id=1, tenant_id=1)`, asserts `.content` matches what was created
   - `test_get_activity_not_found` — calls `get_activity(9999, tenant_id=1)`, expects `NotFoundException`
   - `TestUpdateActivity` class with `test_update_activity` — pre-populate mock result for `session.execute` so that `_fetch` returns a row; call `update_activity(id=1, tenant_id=1, content="Updated content")`; assert returned activity `.content == "Updated content"`
   - `TestDeleteActivity` class with `test_delete_activity` — pre-populate mock result for `_fetch` to find the row; call `delete_activity(id=1, tenant_id=1)`; assert returned dict has `{"id": 1}`; subsequent `get_activity(1, tenant_id=1)` raises `NotFoundException`
   - `TestListActivitiesPagination` class with `test_list_activities_pagination` — mock `session.execute` to return two `MockRow` instances for the SELECT and `[[3]]` for the COUNT; call `list_activities(tenant_id=1, page=1, page_size=2)`; assert `items` has `len == 2` and `total == 3`

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_activity_service.py` — 6 new test cases covering `create_activity`, `get_activity` (found + not found), `update_activity`, `delete_activity`, and `list_activities` pagination
- **Integration tests in `tests/integration/`**: No integration tests required for this task

## Acceptance Criteria

- `pytest tests/unit/test_activity_service.py --collect-only` reports exactly 6 collected items with 0 errors
- `pytest tests/unit/test_activity_service.py -v` — all 6 tests pass
- `pytest tests/unit/ -q` — the full unit suite (including new tests) remains green with no failures
- `ruff check src/` passes with no new violations
- `ruff format --check src/` passes with no new violations

## Risks / Open Questions

- The issue description refers to `ApiResponse` in `test_create_activity_returns_api_response`, but `ActivityService.create_activity` returns an `Activity` domain object directly — the test should assert on the returned `Activity` fields (`.content`, `.type`, `.id`) consistent with all other service tests in the suite
- No activity handler exists in `conftest.py` yet — step 2 must be completed before the test file can pass; no other files depend on `make_activity_handler`, so adding it has no risk of breaking existing tests
