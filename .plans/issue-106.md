I have all the information needed. Here is the implementation plan:

# Implementation Plan — Issue #106

## Goal

Create `src/api/routers/tasks.py` exposing the 6 REST endpoints defined in the issue, wire it into `src/api/__init__.py` and `src/main.py`, and add test coverage so the frontend Task Board UI can call `/api/v1/tasks` without returning 404.

## Affected Files

- `src/api/routers/tasks.py` — **new** — FastAPI router for all task endpoints
- `src/api/__init__.py` — add `tasks_router` import and export
- `src/main.py` — register `tasks_router` via `app.include_router(tasks_router)`
- `tests/unit/test_tasks.py` — **new** — unit tests for router + service integration
- `tests/integration/test_tasks_integration.py` — **new** — integration tests against real PostgreSQL

## Implementation Steps

1. **Create `src/api/routers/tasks.py`**
   - Import `TaskService` from `services.task_service`, `AuthContext`/`require_auth` from `internal.middleware.fastapi_auth`, `get_db` from `db.connection`
   - Define `tasks_router = APIRouter(prefix="/api/v1", tags=["tasks"])`
   - Add request schemas: `TaskCreate`, `TaskUpdate` (both Pydantic `BaseModel` with `Field` constraints matching service expectations — `title` required, `description` default empty string, `assigned_to` default 0, `due_date` optional, `priority` optional)
   - Implement endpoints mirroring `tickets.py` pattern:
     - `POST /tasks` → `status_code=201` → calls `svc.create_task(...)`
     - `GET /tasks` → `page`, `page_size`, `status` as `Query` params → calls `svc.list_tasks(...)`
     - `GET /tasks/{task_id}` → calls `svc.get_task(...)`
     - `PATCH /tasks/{task_id}` → `body: TaskUpdate` → calls `svc.update_task(...)`
     - `POST /tasks/{task_id}/complete` → calls `svc.complete_task(...)`
     - `DELETE /tasks/{task_id}` → calls `svc.delete_task(...)`
   - All endpoints inject `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`, pass `tenant_id=ctx.tenant_id or 0` to service
   - Serialise service return values with `.to_dict()` before returning `{"success": True, "data": ...}`
   - Reuse the `_paginated` helper pattern from `tickets.py` for `GET /tasks`

2. **Register `tasks_router` in `src/api/__init__.py`**
   - Add `from api.routers.tasks import tasks_router`
   - Add `"tasks_router"` to the `__all__` list

3. **Mount the router in `src/main.py`**
   - Add `tasks_router` to the `from api import (...)` line
   - Add `app.include_router(tasks_router)` in the routes section (after `tickets_router`)

4. **Add `make_task_handler(state: MockState)` to `tests/unit/conftest.py`**
   - Factory function returning a handler, following the same pattern as `make_customer_handler` and `make_user_handler`
   - Handles: `INSERT INTO tasks`, `SELECT FROM tasks WHERE id`, `SELECT FROM tasks` (list), `UPDATE tasks`, `DELETE FROM tasks`, `SELECT COUNT FROM tasks`
   - Stores tasks in `state.tasks: dict[int, dict]` with `state.tasks_next_id: int`

5. **Create `tests/unit/test_tasks.py`**
   - Fixture `mock_db_session`: composes `make_task_handler(state)` + `make_count_handler(state)` via `make_mock_session`
   - Fixture `task_service`: returns `TaskService(mock_db_session)`
   - Tests:
     - `test_create_task` → calls service, asserts returned object has `id`
     - `test_get_task` → creates task then fetches by id, asserts `.to_dict()` shape
     - `test_get_task_not_found` → `pytest.raises(NotFoundException)`
     - `test_update_task` → updates title/status, asserts change reflected
     - `test_complete_task` → marks task done, asserts `status == "completed"`
     - `test_delete_task` → deletes, asserts `NotFoundException` on subsequent fetch
     - `test_list_tasks` → creates multiple tasks, lists with pagination, asserts count

6. **Create `tests/integration/test_tasks_integration.py`**
   - Uses `db_schema`, `tenant_id`, `async_session` fixtures (same pattern as existing integration tests)
   - Tests:
     - `test_create_task` → `POST /api/v1/tasks`, expects `201` and response shape
     - `test_list_tasks` → creates 3 tasks, `GET /api/v1/tasks`, asserts `total >= 3`
     - `test_list_tasks_with_status_filter` → creates `pending` and `completed` tasks, filters by `status=pending`
     - `test_get_task` → creates task, `GET /api/v1/tasks/{id}`, asserts data
     - `test_update_task` → `PATCH /api/v1/tasks/{id}`, asserts updated fields
     - `test_complete_task` → `POST /api/v1/tasks/{id}/complete`, asserts `status == "completed"`
     - `test_delete_task` → `DELETE /api/v1/tasks/{id}`, asserts `404` on subsequent GET
     - `test_unauthenticated_returns_401` → no auth context, expects 401
   - Each test uses `async with AsyncSession(...) as session:` or the `async_session` fixture

## Test Plan

- **Unit tests in `tests/unit/`**: `test_tasks.py` — covers `TaskService` via `TaskService(mock_session)` using a new `make_task_handler` in conftest; no real DB, fast (~1s)
- **Integration tests in `tests/integration/`**: `test_tasks_integration.py` — covers all 6 REST endpoints against real PostgreSQL using `db_schema` fixture; full TRUNCATE CASCADE between tests

## Acceptance Criteria

- `POST /api/v1/tasks` returns `201` with `{"success": true, "data": {"id": ..., "title": ...}}`
- `GET /api/v1/tasks` returns paginated list `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20}}`
- `GET /api/v1/tasks?status=pending` returns only tasks with that status
- `GET /api/v1/tasks/:id` returns task object; returns `404` for non-existent id
- `PATCH /api/v1/tasks/:id` updates and returns the updated task object
- `POST /api/v1/tasks/:id/complete` sets `status = "completed"` and returns updated task
- `DELETE /api/v1/tasks/:id` returns `200`; subsequent `GET` returns `404`
- All endpoints return `401` without valid auth context (multi-tenancy enforcement)
