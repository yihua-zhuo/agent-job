# Implementation Plan — Issue #622

## Goal

Create `src/api/routers/agent_tasks.py` exposing `POST /agents/tasks`, `GET /agents/tasks` (with `?status=` and `?date_from=&date_to=` filters), and `GET /agents/tasks/{task_id}` — wiring through the `AgentTaskService` (from #621 dependency) using the project's standard Router Pattern (`AuthContext = Depends(require_auth)`, `session: AsyncSession = Depends(get_db)`, no try/catch, serialisation via `.to_dict()` and `{"success": True, "data": ...}` envelope).

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0622-add-post-and-get-agents-tasks-router-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0622-add-post-and-get-agents-tasks-router-endpoints.md`

## Affected Files

- `src/api/routers/agent_tasks.py` — **new** — router with three endpoints
- `tests/unit/test_agent_tasks.py` — **new** — unit tests using `httpx.AsyncClient` + mocked `AgentTaskService`
- `tests/integration/test_agent_tasks_integration.py` — **new** — integration tests against real PostgreSQL
- `src/main.py` — no change required (routers are auto-discovered via `src/api/__init__.py`'s `iter_routers()`)

## Implementation Steps

### Step 1: Create `src/api/routers/agent_tasks.py`

Follow the same pattern as [`src/api/routers/tasks.py`](src/api/routers/tasks.py) (the canonical router template in this codebase). The `api/__init__.py` `iter_routers()` auto-discovers all routers — no manual `app.include_router()` call needed.

**File structure:**
- `agent_tasks_router = APIRouter(prefix="/agents/tasks", tags=["Agent Tasks"])`
- `POST /` — request body `{"description": str}`, calls `svc.create_task(description, tenant_id=ctx.tenant_id)`, returns `201 {"success": True, "data": task.to_dict()}`
- `GET /` — query params `status: str | None`, `date_from: date | None`, `date_to: date | None`, `page: int = Query(1, ge=1)`, `page_size: int = Query(20, ge=1, le=100)` — calls `svc.list_tasks(tenant_id, status, date_from, date_to, page, page_size)`, returns paginated envelope
- `GET /{task_id}` — calls `svc.get_task(task_id, tenant_id=ctx.tenant_id)`, returns `200 {"success": True, "data": task.to_dict()}` or raises `NotFoundException` → global handler returns 404

**Key imports** (all verified to exist in the codebase):
- `from services.agent_task_service import AgentTaskService` — already exists at [`src/services/agent_task_service.py`](src/services/agent_task_service.py)
- `from db.connection import get_db` — confirmed in [`src/db/connection.py`](src/db/connection.py)
- `from internal.middleware.fastapi_auth import AuthContext, require_auth` — confirmed in `test_tasks.py` imports
- `AgentTaskService.create_task(description: str, tenant_id: int)` — L29-45
- `AgentTaskService.list_tasks(tenant_id, status, date_from, date_to, page, page_size)` — L61-93
- `AgentTaskService.get_task(task_id, tenant_id)` — L47-59

**完成判定**：`PYTHONPATH=src python -c "from api.routers.agent_tasks import agent_tasks_router; print('import ok')"` → exit 0

---

### Step 2: Create `tests/unit/test_agent_tasks.py`

Mirror the pattern from [`tests/unit/test_tasks.py`](tests/unit/test_tasks.py) (lines 76-115). Use `FastAPI()`, `app.include_router(agent_tasks_router)`, `app.dependency_overrides[require_auth]`, `app.dependency_overrides[get_db]`, and `httpx.AsyncClient(ASGITransport(...))`. Mock `AgentTaskService` entirely (do NOT use `make_mock_session` — the service layer is already unit-tested in `test_agent_task_service.py`).

**Test cases (≥ 5):**
1. `POST /agents/tasks` — `description` provided → 201 + `{"success": true, "data": {"description": ..., "status": "pending", "task_id": ...}}`
2. `POST /agents/tasks` — empty/whitespace description → 422 (Pydantic validation via service `ValidationException`)
3. `GET /agents/tasks` — no filters → 200 + paginated envelope (`items`, `total`, `page`, `page_size`, `has_next`)
4. `GET /agents/tasks?status=pending` → 200, service called with `status="pending"`
5. `GET /agents/tasks?date_from=2026-01-01&date_to=2026-05-31` → 200, date bounds passed to service
6. `GET /agents/tasks/{task_id}` — task exists → 200 + full dict
7. `GET /agents/tasks/{task_id}` — task not found → 404 via global `NotFoundException` handler

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_tasks.py -v` → all passed

---

### Step 3: Create `tests/integration/test_agent_tasks_integration.py`

Mirror the pattern from [`tests/integration/test_tasks_integration.py`](tests/integration/test_tasks_integration.py). Use fixtures `db_schema`, `tenant_id_web`, `async_session` (from `tests/integration/conftest.py`). Call through the real FastAPI stack via `api_client` fixture. Seed data directly into DB (no service-level seeding helpers needed for this scope).

**Test cases:**
1. `POST /agents/tasks` → 201 + `task_id` non-null, `status="pending"`, tenant isolation verified
2. `GET /agents/tasks` → 200, `items` list contains created task, `total >= 1`
3. `GET /agents/tasks?status=pending` → filters correctly
4. `GET /agents/tasks/{id}` → 200 with correct data
5. `GET /agents/tasks/99999` → 404

**完成判定**：`DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → all passed

---

### Step 4: Lint and type-check

- `ruff check src/api/routers/agent_tasks.py tests/unit/test_agent_tasks.py` → 0 errors
- `ruff format --check src/api/routers/agent_tasks.py` → must pass

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_agent_tasks.py` — covers all three router endpoints with success paths, validation failures (422), and not-found paths (404 via global handler). Service layer is already tested in `tests/unit/test_agent_task_service.py`.
- **Integration tests in `tests/integration/`**: `tests/integration/test_agent_tasks_integration.py` — full-stack via `api_client` fixture against real PostgreSQL, covering 201 creation, 200 list retrieval, status/date filtering, and 404 responses.
- **Dev-plan verification** (from board §6):
  - `ruff check src/api/routers/agent_tasks.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_agent_tasks.py -v` → all passed (≥ 5用例)
  - `PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → all passed
  - `python -c "from api.routers.agent_tasks import agent_tasks_router; print('import ok')"` → exit 0
  - `python -c "from main import app; print('/agents/tasks' in [r.path for r in app.routes])"` → True

## Acceptance Criteria

- `src/api/routers/agent_tasks.py` exists and exports `agent_tasks_router` (an `APIRouter` instance)
- `POST /agents/tasks` accepts `{"description": "..."}` JSON body, returns 201 with `task_id`, `subtasks`, `status` fields
- `GET /agents/tasks` accepts `?status=` and `?date_from=` / `?date_to=` query params, returns paginated envelope with `items`/`total`/`page`/`page_size`/`has_next`
- `GET /agents/tasks/{task_id}` returns 200 with full task dict or 404 via global handler
- All three endpoints inject `tenant_id` from `AuthContext` (multi-tenancy enforced at service layer)
- No `try/except` blocks in the router; `AppException` caught by `main.py` global handlers
- `.to_dict()` called in router, not in service
- `ruff check` and `ruff format --check` both pass on the new router file
- Unit tests ≥ 5 passed, integration tests all passed

## Risks / Open Questions

- None — the `AgentTaskService` from #621 is already implemented and its mock handler (`make_agent_task_handler`) exists in `tests/unit/domain_handlers/agent_tasks.py`, so the router can be built and tested without further coordination.
