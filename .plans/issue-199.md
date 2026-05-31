Now I have everything I need. Let me write the implementation plan grounded in the actual codebase.

# Implementation Plan — Issue #199

## Goal
Add `tests/unit/test_activity_service.py` with 6 unit tests covering the core CRUD methods of `ActivityService`. Tests run against in-memory mocks — no `DATABASE_URL` required.

## Affected Files
- `tests/unit/test_activity_service.py` — **new file**, contains all 6 tests
- `src/services/activity_service.py` — read-only (implementation already exists)

## Implementation Steps

1. **Create `tests/unit/test_activity_service.py`** with a `MockActivityModel` class mirroring `ActivityModel` (id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at, to_dict) and a `MockResult` helper that returns rows via `scalar_one_or_none` and `scalars().all()`.

2. **Add a `mock_session` fixture** that wires `session.execute` to `AsyncMock`, `session.flush` to `AsyncMock`, `session.add` to `MagicMock`, `session.refresh` to `AsyncMock`, and drives the mock by calling `mock_session.execute.side_effect` with a list of `MockResult` objects. A `activity_service` fixture depends on `mock_session` and returns `ActivityService(mock_session)`.

3. **Write `test_create_activity_returns_activity`** (NOT ApiResponse — services return domain objects per project convention). After `create_activity`, assert `result.id` is not None, `result.content` matches, `result.type` is `ActivityType.CALL`. Mock `_fetch` (refresh) to set `row.id`. Assert `session.add` was called once and `session.flush` was called once.

4. **Write `test_create_activity_invalid_type_raises`** — pass `activity_type="invalid"` and assert `ValidationException` is raised with a match on "无效的活动类型".

5. **Write `test_get_activity_found`** — pre-populate `side_effect` with `[row1]` where `row1` is a `MockActivityModel` matching what `_to_activity` expects. Call `get_activity(id=1, tenant_id=1)` and assert `result.content == "Test content"`.

6. **Write `test_get_activity_not_found`** — set `side_effect = [MockResult([])]`. Assert `NotFoundException` ("活动记录") is raised.

7. **Write `test_update_activity`** — set `side_effect = [MockResult([row1]), MockResult([row1_updated])]` where the second row has updated content. Call `update_activity(id=1, tenant_id=1, content="Updated")` and assert `result.content == "Updated"`.

8. **Write `test_delete_activity`** — `side_effect = [MockResult([row1]), MockResult([])]`. Call `delete_activity(id=1, tenant_id=1)` and assert the returned dict equals `{"id": 1}`. Subsequent `get_activity` call then fails with `NotFoundException`.

9. **Write `test_list_activities_pagination`** — `side_effect = [MockResult([], total=3), MockResult([row1, row2])]` where the first `MockResult` mocks the `func.count()` scalar and the second mocks the paginated select. Call `list_activities(tenant_id=1, page=1, page_size=2)` and assert `len(items) == 2` and `total == 3`.

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_activity_service.py` — 6 tests for `ActivityService` core CRUD, no DB required
- Integration tests in `tests/integration/`: none required for this task

## Acceptance Criteria
- `pytest tests/unit/test_activity_service.py -v` — all 6 tests pass
- No `DATABASE_URL` environment variable referenced anywhere in the file
- `activity_service` fixture creates a fresh `ActivityService(mock_session)` per test (function-scoped)
- All async test methods use `pytest.mark.asyncio` decorator
- `create_activity` returns an `Activity` domain object (NOT `ApiResponse`)
- `list_activities` returns `tuple[list[Activity], int]` — assert on `.items` list length and total count directly
- `delete_activity` returns `{"id": int}` — assert on dict key/value, not on an `Activity` object
- `get_activity` raises `NotFoundException("活动记录")` for unknown IDs — assert with `pytest.raises(NotFoundException)`
- `create_activity` raises `ValidationException` for unknown `activity_type` strings — assert with `pytest.raises(ValidationException)`
- `activity_type` string values in test calls must match `ActivityType` enum values exactly: `"call"`, `"email"`, `"meeting"`, `"note"`

## Risks / Open Questions
- `delete_activity` returns `dict` (not `Activity`) — not a risk but a deviation from the `create/get/update` pattern; test must assert on the dict directly.
- `list_activities` calls `session.execute` twice per invocation (count then select) — `side_effect` list must have exactly 2 entries in the correct order for pagination tests.
