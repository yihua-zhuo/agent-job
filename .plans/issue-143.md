# Implementation Plan — Issue #143

## Goal

Add a `tests/unit/test_activity_service.py` unit test suite for `ActivityService` covering all core CRUD operations and pagination, matching the patterns used by existing unit tests in the project.

## Affected Files

- `tests/unit/conftest.py` — add `activities` dict + `activities_next_id` to `MockState`, add `make_activity_handler(state)` factory, register it in `all_handlers()`
- `tests/unit/test_activity_service.py` — **new file** — `mock_db_session` fixture + 13 test methods across 5 classes

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
   - Import `ActivityService`, `ActivityType` from `src`, plus `NotFoundException` and `ValidationException`
   - `mock_db_session` fixture built from `make_mock_session([make_activity_handler(activity_state)])`; `session.refresh` side-effects `obj.id` assignment for unsaved records
   - `activity_service` fixture: `return ActivityService(mock_db_session)`
   - `TestCreateActivity` class with:
     - `test_create_activity_returns_activity` — calls `create_activity`, asserts returned `Activity` has `.content == "Test call"` and `.type == ActivityType.CALL`
     - `test_create_activity_rejects_invalid_type` — calls with `activity_type="invalid"`, expects `ValidationException`
   - `TestGetActivity` class with:
     - `test_get_activity_found` — pre-seeds an activity via `add_activity`, calls `get_activity`, asserts `.content == "Test call"`
     - `test_get_activity_not_found` — calls `get_activity(9999, tenant_id=1)`, expects `NotFoundException`
     - `test_get_activity_rejects_wrong_tenant` — seeds activity for `tenant_id=2`, calls with `tenant_id=1`, expects `NotFoundException`
   - `TestUpdateActivity` class with:
     - `test_update_activity` — seeds activity, calls `update_activity(id=1, content="Updated content")`, asserts `.content == "Updated content"`
     - `test_update_activity_with_no_fields_only_refetches` — seeds activity, calls with no fields, asserts `execute.await_count == 2` and `flush` not called
     - `test_update_activity_rejects_invalid_type` — seeds activity, calls with `activity_type="invalid"`, expects `ValidationException`
     - `test_update_activity_rejects_wrong_tenant` — seeds activity for `tenant_id=2`, calls with `tenant_id=1`, expects `NotFoundException` and original content unchanged
   - `TestDeleteActivity` class with:
     - `test_delete_activity` — seeds activity, calls `delete_activity`, asserts returned `{"id": 1}` and subsequent `get_activity` raises `NotFoundException`
     - `test_delete_activity_rejects_wrong_tenant` — seeds activity for `tenant_id=2`, calls with `tenant_id=1`, expects `NotFoundException` and record unchanged
   - `TestListActivitiesPagination` class with:
     - `test_list_activities_pagination` — seeds 3 activities for `tenant_id=1` and 1 for `tenant_id=2`; calls `list_activities(tenant_id=1, page=1, page_size=2)`; asserts `len(items) == 2` and `total == 3`
     - `test_list_activities_filters_customer_and_type` — seeds 3 activities with mixed customer/type; calls with `customer_id=1, activity_type="call"`; asserts `total == 1` and returned item id is correct

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_activity_service.py` — 13 test methods covering `create_activity` (2), `get_activity` (3), `update_activity` (4), `delete_activity` (2), and `list_activities` pagination/filtering (2)
- **Integration tests in `tests/integration/`**: No integration tests required for this task

## Acceptance Criteria

- `pytest tests/unit/test_activity_service.py --collect-only` reports exactly 13 collected items with 0 errors
- `pytest tests/unit/test_activity_service.py -v` — all 13 tests pass
- `pytest tests/unit/ -q` — the full unit suite (including new tests) remains green with no failures
- `ruff check src/` passes with no new violations
- `ruff format --check src/` passes with no new violations

## Risks / Open Questions

- No activity handler exists in `conftest.py` yet — step 2 must be completed before the test file can pass; no other files depend on `make_activity_handler`, so adding it has no risk of breaking existing tests
