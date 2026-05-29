Now I have a complete picture of the codebase. Here is the implementation plan:

---

# Implementation Plan — Issue #485

## Goal

Add the two missing methods to `ActivityService` (`get_recent_activities` and `get_activity_by_type`) and wire them up to FastAPI router endpoints so they are accessible via the API. Both methods filter by `tenant_id` for multi-tenancy safety.

## Affected Files

- `src/services/activity_service.py` — add `get_recent_activities` and `get_activity_by_type` methods
- `src/api/routers/activities.py` — add `GET /recent` and `GET /by-type/{activity_type}` endpoints
- `tests/unit/domain_handlers/activities.py` — extend `make_activity_handler` to handle the new SQL patterns (ORDER BY with limit, and WHERE type filter)
- `tests/unit/test_activity_service.py` — add `TestGetRecentActivities` and `TestGetActivityByType` classes

## Implementation Steps

1. **Add `get_recent_activities` to `ActivityService`** (`src/services/activity_service.py`): Accept `tenant_id: int` and `limit: int`; query `ActivityModel` filtered by `tenant_id`, ordered by `created_at.desc()`, limited; return `list[Activity]`. Raise nothing.

2. **Add `get_activity_by_type` to `ActivityService`** (`src/services/activity_service.py`): Accept `tenant_id: int` and `activity_type: str`; validate the type via `ActivityType(activity_type)`, raising `ValidationException` on invalid input; query filtered by `tenant_id` and `type`, ordered by `created_at.desc()`; return `list[Activity]`.

3. **Extend `make_activity_handler`** (`tests/unit/domain_handlers/activities.py`): The existing handler already supports tenant filtering and `activity_type` filtering. Ensure it also handles ORDER BY + LIMIT queries (the recent activities pattern) so the new SQL from steps 1–2 can be exercised in unit tests.

4. **Add `GET /recent` endpoint** (`src/api/routers/activities.py`): Accept `limit: int = Query(10, ge=1, le=100)`, inject `AuthContext` and session; call `ActivityService(session).get_recent_activities(tenant_id=ctx.tenant_id, limit=limit)`; return `{"success": True, "data": [a.to_dict() for a in activities]}`.

5. **Add `GET /by-type/{activity_type}` endpoint** (`src/api/routers/activities.py`): Accept `activity_type: str` path param (validated by service), inject `AuthContext` and session; call `ActivityService(session).get_activity_by_type(tenant_id=ctx.tenant_id, activity_type=activity_type)`; return `{"success": True, "data": [a.to_dict() for a in activities]}`.

## Test Plan

- `tests/unit/test_activity_service.py`: Add two test classes that use the existing `mock_db_session` fixture (which wraps `make_activity_handler`):
  - `TestGetRecentActivities`: test returns activities sorted `created_at desc`, test respects `limit`, test returns only the calling tenant's activities (cross-tenant isolation), test returns empty list when no activities exist.
  - `TestGetActivityByType`: test returns activities matching the given `ActivityType` value, test raises `ValidationException` for an invalid type string, test returns only the calling tenant's activities, test returns activities sorted `created_at desc`.

## Acceptance Criteria

- `ActivityService.get_recent_activities(tenant_id, limit)` returns at most `limit` activities for the given tenant, ordered newest-first.
- `ActivityService.get_activity_by_type(tenant_id, activity_type)` returns all activities of the given type for the tenant, ordered newest-first; raises `ValidationException` for an unknown type string.
- Both service methods raise `NotFoundException` when a non-existent activity_id is passed (delegated to `_fetch` for that path); for type validation they raise `ValidationException`.
- `GET /api/v1/activities/recent?limit=N` calls the service and serializes results via `.to_dict()`.
- `GET /api/v1/activities/by-type/{activity_type}` calls the service and serializes results via `.to_dict()`.
- All unit tests pass: `pytest tests/unit/ -v`.

## Risks / Open Questions

- The mock SQL handler in `tests/unit/domain_handlers/activities.py` uses string matching on the SQL text to branch on different query shapes. If the generated SQL varies in whitespace or column order between the existing queries and the new ones, the handler may not route correctly. Verify by running the new unit tests before considering this done.
