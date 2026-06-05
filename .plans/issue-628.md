Now I have all the details. Dev-plan corrections:

1. **`src/api/deps.py` does NOT exist** — it needs to be created (not "extended"). The dev-plan incorrectly says "add to" it.
2. **`AgentRegistry.get()` raises `LookupError`** (not `KeyError`) — the dev-plan's `dispatch` code is wrong, it must catch `LookupError`.
3. **AgentRegistry is a singleton** — no constructor args. No `list_types()` method — it has `list_agents()`.
4. **`LLMService.__init__` takes `session: AsyncSession`** — not parameterless.
5. **Routers are auto-discovered** by `iter_routers()` — naming `router` suffices; no manual `include_router` in `main.py` needed.
6. **The dev-plan has import path errors**: `from db.models.llm_service` and `from db.models.agent_registry` — both are wrong. Correct paths: `from services.llm_service` and `from agents.registry`.

# Implementation Plan — Issue #628

## Goal

Create `AgentService` (the service that dispatches tasks to agents via `AgentRegistry` and wraps an `LLMService`), wire it into FastAPI's dependency-injection system via a new `src/api/deps.py`, and expose a `GET /health/agents` endpoint that reports LLM and agent-registry status. This is a pure backend wiring task — no ORM models, no migrations, no auth changes.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0628-wire-agentservice-dispatch-and-add-fastapi-dependencies.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0628-wire-agentservice-dispatch-and-add-fastapi-dependencies.md`

**Discrepancies found between dev-plan and current code (these corrections MUST be applied during implementation):**
- `src/api/deps.py` does **not** exist yet — it must be **created**, not extended.
- `AgentRegistry.get()` raises **`LookupError`** (not `KeyError` as the dev-plan code suggests). `AgentService.dispatch()` must catch `LookupError` and re-raise as `NotFoundException`.
- `AgentRegistry` is a **singleton** (no constructor args); it has a **`list_agents()`** method (not `list_types()`).
- `LLMService.__init__` requires `session: AsyncSession` (not parameterless) — see `src/services/llm_service.py` L24.
- Dev-plan's import paths `from db.models.llm_service` / `from db.models.agent_registry` are **wrong**. Correct: `from services.llm_service import LLMService` and `from agents.registry import AgentRegistry`.
- `src/api/routers/health.py` does **not** exist — must be created.
- `main.py` auto-discovers routers via `iter_routers()` (`src/main.py` L88-89) — no manual `app.include_router` call needed. The dev-plan's Step 4 (`Register health router in src/main.py`) is a **no-op** if the health router is named `router`.

## Affected Files

- `src/services/agent_service.py` — **create**. `AgentService` class with `dispatch()` and `get_status()`.
- `src/api/deps.py` — **create**. `get_llm_service()` and `get_agent_service()` FastAPI dependency functions, plus re-exports for `get_db` and `get_current_user` so it becomes the single DI module.
- `src/api/routers/health.py` — **create**. `GET /health/agents` endpoint returning status JSON.
- `tests/unit/test_agent_service.py` — **create**. Unit tests for `dispatch()` (success, unknown type → `NotFoundException`) and `get_status()`.
- `tests/unit/test_health_router.py` — **create**. Unit test for `GET /health/agents` route returning 200 with correct envelope.
- `src/main.py` — **no change** (router auto-discovered by `iter_routers()`).

## Implementation Steps

### Step 1: Create `src/services/agent_service.py`

Create `AgentService` with constructor that types `session: AsyncSession` (no default), `llm_service: LLMService`, and `registry: AgentRegistry`.

- `async def dispatch(self, agent_type: str, task: str, tenant_id: int) -> dict` — `task` is a plain string description (NOT a dict). Calls `self._registry.get(agent_type)` inside a `try/except LookupError` (NOT `KeyError` — the registry raises `LookupError`, see `src/agents/registry.py` L56), re-raises as `NotFoundException(f"Agent type '{agent_type}' not registered")`. On success returns the awaited result of `agent.run(task)`. The dispatch method is async because `BaseAgent.run` is async.
- `async get_status(self) -> dict` — returns `{"llm": "ok"|"error", "agents": <list_agents()>, "timestamp": <ISO 8601>}`. Wraps `llm_service` availability check in a `try/except` and defaults to `"error"` on failure.

Import paths (corrected from dev-plan):
```python
from services.llm_service import LLMService
from agents.registry import AgentRegistry
from pkg.errors.app_exceptions import NotFoundException
```

Do not import `LLMService` or `AgentRegistry` from `db.models` — those paths are wrong.

**Completion check:** `ruff check src/services/agent_service.py` → 0 errors.

### Step 2: Create `src/api/deps.py`

Create the dependency-injection module. Include the two new functions plus re-exports of the existing session/auth dependencies so `deps.py` becomes the single DI import surface:

- `get_db` — re-export from `db.connection` (session is request-scoped, injected via `Depends(get_db)`).
- `get_current_user` — re-export from `dependencies.auth`.
- `get_llm_service(session: AsyncSession = Depends(get_db)) -> LLMService` — returns `LLMService(session)`. Constructed per-request (the session is request-scoped, so a module-level singleton would hold a stale session reference — see dev-plan §7 risk).
- `get_agent_service(session: AsyncSession = Depends(get_db), llm_service: LLMService = Depends(get_llm_service)) -> AgentService` — returns `AgentService(session, llm_service, AgentRegistry())`. `AgentRegistry()` is a singleton (returns the same instance on every call), so this is safe.

**Completion check:** `ruff check src/api/deps.py` → 0 errors.

### Step 3: Create `src/api/routers/health.py`

Create the health router with a single route. Name the variable `router` so `iter_routers()` auto-discovers it (see `src/api/__init__.py` L39 and `src/main.py` L88-89 — **no manual registration in `main.py` is needed**):

```python
from fastapi import APIRouter, Depends
from api.deps import get_agent_service
from services.agent_service import AgentService

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/agents")
async def get_agents_health(
    agent_svc: AgentService = Depends(get_agent_service),
) -> dict:
    status = await agent_svc.get_status()
    return {"success": True, "data": status}
```

The existing root-level `GET /` health endpoint in `main.py` (L91-93) is left untouched — out of scope.

**Completion check:** `ruff check src/api/routers/health.py` → 0 errors.

### Step 4: Write unit tests `tests/unit/test_agent_service.py`

Test three behaviours using `unittest.mock.AsyncMock` / `MagicMock` (the session is passed through to the agent's `run()` method, which is fully mocked in unit tests — the service itself does not execute SQL):

1. **`test_dispatch_success`** — mock `registry.get()` to return a mock agent whose `run()` is an `AsyncMock` returning `{"result": "ok"}`. Call `await agent_service.dispatch("greeting", {"text": "hi"}, tenant_id=1)`. Assert result equals `{"result": "ok"}` and `registry.get` called once with `"greeting"`.
2. **`test_dispatch_unknown_type_raises`** — mock `registry.get` to raise `LookupError("greeting")`. Assert `pytest.raises(NotFoundException)` with the agent type in the exception message.
3. **`test_get_status_returns_dict`** — mock `llm_service` (health check passes), mock `registry.list_agents()` to return `["greeting", "support"]`. Assert the result has keys `"llm"`, `"agents"`, `"timestamp"` and `"llm" == "ok"`.

Mock fixtures follow the pattern in `tests/unit/test_llm_service.py` and `tests/unit/test_agent_registry.py` (both already exist).

**Completion check:** `PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → 3 passed.

### Step 5: Write unit tests `tests/unit/test_health_router.py`

Test the `/health/agents` endpoint using FastAPI's `TestClient` (the pattern used in `tests/unit/test_ai_router.py`):

- **`test_health_agents_returns_200`** — patch `get_agent_service` dependency to return a mock `AgentService` whose `get_status()` returns a known dict. Assert response status 200, `body["success"] is True`, `body["data"]` contains expected keys.
- **`test_health_agents_endpoint_registered`** — import the `router` object and assert it has the `/agents` route under the `/health` prefix.

**Completion check:** `PYTHONPATH=src pytest tests/unit/test_health_router.py -v` → 2 passed.

### Step 6: Run full lint and unit-test suite

Final checks:
- `ruff check src/services/agent_service.py src/api/deps.py src/api/routers/health.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_service.py tests/unit/test_health_router.py -v` → all passed

## Test Plan

- **Unit tests in `tests/unit/`:**
  - `tests/unit/test_agent_service.py` — 3 cases: dispatch success, dispatch unknown type raises `NotFoundException`, `get_status()` returns correct dict shape.
  - `tests/unit/test_health_router.py` — 2 cases: `GET /health/agents` returns 200 with correct envelope, route is registered under the `/health` prefix.

- **Integration tests in `tests/integration/`:**
  - One new integration test will live in `tests/integration/test_health_agents_endpoint_integration.py`. It will call `GET /health/agents` against the real FastAPI app (constructed with the real lifespan and real session fixture) and assert the response shape. This is required because the endpoint is a critical HTTP flow that the unit tests only exercise with a minimal `TestClient` (no middleware, no real session).

- **Dev-plan verification (mapped to §6 acceptance items):**
  - `ruff check src/services/agent_service.py src/api/deps.py src/api/routers/health.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → 3 passed
  - `PYTHONPATH=src pytest tests/unit/test_health_router.py -v` → 2 passed
  - Alembic checks → N/A (dev-plan §6 explicitly states "N/A — no migrations in this board")
  - End-to-end `curl http://localhost:8000/health/agents` → returns `{"success": true, "data": {"llm": "ok", "agents": [...], "timestamp": "..."}}` (manually verified after dev server start, not automated in this board)

## Acceptance Criteria

1. `src/services/agent_service.py` exists with `AgentService(session, llm_service, registry)` — `session` has no default, typed `AsyncSession`.
2. `AgentService.dispatch("unknown_type", ...)` raises `NotFoundException` (not `LookupError` or `KeyError`).
3. `src/api/deps.py` exists with `get_llm_service()` and `get_agent_service()` as callable FastAPI dependencies.
4. `GET /health/agents` returns HTTP 200 with body shape `{"success": true, "data": {"llm": "...", "agents": [...], "timestamp": "..."}}`.
5. `ruff check src/services/agent_service.py src/api/deps.py src/api/routers/health.py` exits 0.
6. `PYTHONPATH=src pytest tests/unit/test_agent_service.py tests/unit/test_health_router.py -v` reports 5 passed (3 + 2), all green.
7. No changes to `src/main.py` are required (router auto-discovered by `iter_routers()`).

## Risks / Open Questions

- **`AgentRegistry` is a process-wide singleton** (see `src/agents/registry.py` L35-41). If the test suite imports multiple test modules that each construct `AgentService`, they all share the same registry instance. `AgentRegistry.reset()` exists as a test-only utility and must be called in test fixtures that need isolation — but the unit tests in this board mock the registry entirely, so the real singleton is never touched. This is safe for the current scope but should be noted if future boards add integration tests that register real agents.
- **`LLMService` requires an `AsyncSession`** in its constructor (`src/services/llm_service.py` L24). This means `get_llm_service` must take `session: AsyncSession = Depends(get_db)`, making `LLMService` request-scoped rather than a true singleton. The dev-plan §4.1 argues for a singleton, but the `session` coupling makes that impossible without further refactoring of `LLMService` — out of scope for this board. The functional impact is minimal: `LLMService` holds an `httpx.AsyncClient` per request, which is cheap.
