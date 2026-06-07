# 自动化 · Wire AgentService dispatch and add FastAPI dependencies

| 元数据 | 值 |
|---|---|
| Issue | #628 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：#627 LLM service and agent registry 板块路径尚未确认 |
| 启用后赋能 | TBD - 待验证：#629 automation rule execution engine 板块路径尚未确认 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

AgentService in `#627` is built but not yet wired into the FastAPI dependency-injection tree. Without `get_llm_service()` / `get_agent_service()` in `deps.py`, router handlers cannot receive an `AgentService` instance cleanly. Additionally, there is no health-check endpoint for AI services, making it impossible to probe LLM and agent availability from the outside.

### 1.2 做完后

- **用户视角**：No direct user-facing changes — this is a pure backend wiring task.
- **开发者视角**：`AgentService` is available via `Depends(get_agent_service)` in any router. The `GET /health/agents` endpoint exposes JSON status of LLM and agent availability. Unknown `agent_type` in `dispatch()` raises `NotFoundException("Agent type '{agent_type}' not registered")`.

### 1.3 不做什么（剔除）

- [ ] No ORM models or migrations — schema changes belong to a dedicated issue.
- [ ] No new LLMService or AgentRegistry implementation — those are delivered in `#627`.
- [ ] No authentication / authorization changes — auth layer is out of scope.
- [ ] No async background task workers (Celery, Redis queues) — those belong to a later issue.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → all passed (≥3 cases: dispatch success, unknown type raises NotFoundException, health endpoint returns 200)
- `ruff check src/services/agent_service.py src/api/deps.py src/api/routers/health.py` → 0 errors
- `PYTHONPATH=src pytest tests/integration/test_agent_service_integration.py -v` → all passed (if integration tests are added in this board)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/llm_service.py L?` — `LLMService` class from #627 (not yet reviewed)

TBD - 待验证：`src/services/agent_registry.py L?` — `AgentRegistry` from #627 (not yet reviewed)

TBD - 待验证：`src/api/deps.py L?` — existing dependency functions (`get_current_user`, `get_db`, etc.) from which this board will add `get_llm_service` and `get_agent_service`

主入口：`src/api/deps.py` (to be extended with new dependency functions)

### 2.2 涉及文件清单

- 要改：
  - `src/api/deps.py` — add `get_llm_service()` and `get_agent_service()` dependency functions
  - `src/api/routers/` — add `health.py` or extend existing health router with `/health/agents` endpoint
- 要建：
  - `src/services/agent_service.py` — `AgentService` class with `dispatch()` and `get_status()`
  - `tests/unit/test_agent_service.py` — unit tests for dispatch and health logic
  - `tests/integration/test_agent_service_integration.py` — integration tests (optional; add if time permits)

### 2.3 缺什么

- [ ] `AgentService` class not yet created — only `LLMService` and `AgentRegistry` stubs exist from #627
- [ ] `get_agent_service()` and `get_llm_service()` not declared in `src/api/deps.py`
- [ ] No `/health/agents` FastAPI route
- [ ] No unit tests for the dispatch routing path
- [ ] `AgentService` does not hold references to both `LLMService` and `AgentRegistry` as required

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/agent_service.py` | `AgentService` with `dispatch(agent_type, task)` and `get_status()` |
| `tests/unit/test_agent_service.py` | Unit tests: dispatch success, unknown type raises NotFoundException, status returns dict |
| `tests/integration/test_agent_service_integration.py` | Integration tests (optional — add only if a DB fixture is warranted) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/api/deps.py` | Add `get_llm_service()` and `get_agent_service()` as FastAPI dependencies |
| `src/api/routers/health.py` | Add `GET /health/agents` returning LLM + agent registry availability |

### 3.3 新增能力

- **Service class**：`AgentService(session: AsyncSession, llm_service: LLMService, registry: AgentRegistry)` — holds references, no `session=None` default
- **Service method**：`AgentService.dispatch(self, agent_type: str, task: Dict, tenant_id: int) -> Dict` — routes to `AgentRegistry.get(agent_type).run(task)`, raises `NotFoundException` for unknown type
- **Service method**：`AgentService.get_status(self) -> Dict` — returns `{"llm": "ok"|"error", "agents": [...], "timestamp": ...}`
- **Dependency function**：`get_llm_service() -> LLMService` in `src/api/deps.py`
- **Dependency function**：`get_agent_service() -> AgentService` in `src/api/deps.py`
- **API endpoint**：`GET /health/agents` → `{"success": true, "data": {"llm": "ok", "agents": [...], "timestamp": "..."}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Singleton LLMService / AgentService over request-scoped** — LLM client holds a connection pool; re-instantiating per request is wasteful. Both services are stateless after construction, so a module-level singleton is appropriate.
- **`dispatch()` returns `Dict` not ORM object** — the result of an agent run is a structured JSON dict (action parameters, message, etc.). Returning `Dict` avoids forcing a domain model on a schema-free output.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `fastapi` | `>=0.110` | Required for `Depends()` caching behaviour used in `deps.py` |
| `httpx` | `>=0.27` | Used by LLMService for LLM API calls; matches FastAPI ecosystem |

### 4.3 兼容性约束

- Service `__init__` takes `session: AsyncSession` with **no default** — never `session=None`.
- Service returns `Dict` / domain objects; never calls `.to_dict()` or returns `ApiResponse`.
- Service errors raise `AppException` subclasses (`NotFoundException` for unknown agent type), never `return {"success": False, ...}`.
- Every SQL query includes `WHERE tenant_id = :tenant_id` (multi-tenancy contract).
- `PYTHONPATH=src` — imports written as `from services.agent_service import ...`, NOT `from src.services.agent_service import ...`.

### 4.4 已知坑

1. **SQLAlchemy `metadata` column name collision** → Not applicable: this board adds no ORM models.
2. **Alembic autogen writes `sa.JSON()` instead of `sa.JSONB()`** → Not applicable: this board adds no migrations.
3. **`dispatch()` must validate `agent_type` before calling `registry.get()`** → If the registry raises a generic `KeyError` instead of `NotFoundException`, the service would leak implementation details. The `AgentService.dispatch()` method must catch the `KeyError` and re-raise as `NotFoundException("Agent type '{agent_type}' not registered")`.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/services/agent_service.py`

Create the `AgentService` class. Constructor takes `session: AsyncSession` (no default), `llm_service: LLMService`, and `registry: AgentRegistry`. The `dispatch` method calls `self.registry.get(agent_type).run(task)` and re-raises `KeyError` as `NotFoundException`. The `get_status` method returns a dict with LLM health and registered agent names.

```python
# src/services/agent_service.py
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.llm_service import LLMService   # TBD - confirm model path from #627
from db.models.agent_registry import AgentRegistry  # TBD - confirm from #627
from pkg.errors.app_exceptions import NotFoundException


class AgentService:
    def __init__(self, session: AsyncSession, llm_service: LLMService, registry: AgentRegistry) -> None:
        self.session = session
        self._llm_service = llm_service
        self._registry = registry

    async def dispatch(self, agent_type: str, task: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
        try:
            agent = self._registry.get(agent_type)
        except KeyError:
            raise NotFoundException(f"Agent type '{agent_type}' not registered")
        return await agent.run(task, tenant_id=tenant_id, session=self.session)

    async def get_status(self) -> Dict[str, Any]:
        llm_ok = True
        try:
            self._llm_service.health_check()
        except Exception:
            llm_ok = False
        return {
            "llm": "ok" if llm_ok else "error",
            "agents": self._registry.list_types(),
            "timestamp": "ISO8601 string",  # use datetime.utcnow().isoformat()
        }
```

**完成判定**：`ruff check src/services/agent_service.py` → 0 errors

### Step 2: Add dependency functions to `src/api/deps.py`

In `src/api/deps.py`, add `get_llm_service()` and `get_agent_service()` as FastAPI `Depends()`-compatible functions. Both are module-level singletons (constructed once, cached by FastAPI's dependency override system).

```python
# src/api/deps.py — add near existing dependency functions
from src.services.llm_service import LLMService
from src.services.agent_service import AgentService
from src.services.agent_registry import AgentRegistry

_llm_service_instance: LLMService | None = None
_agent_service_instance: AgentService | None = None


def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance


def get_agent_service(
    session: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
) -> AgentService:
    global _agent_service_instance
    if _agent_service_instance is None:
        registry = AgentRegistry()  # TBD — confirm AgentRegistry constructor from #627
        _agent_service_instance = AgentService(session, llm_service, registry)
    return _agent_service_instance
```

Note: if `AgentRegistry` requires a database session or other runtime dependency, the `get_agent_service` function must receive it via `Depends()` the same way `session` is received.

**完成判定**：`ruff check src/api/deps.py` → 0 errors

### Step 3: Add `GET /health/agents` endpoint

Create `src/api/routers/health.py` if it does not exist, or append the `/health/agents` route to the existing health router. The endpoint injects `AgentService` via `Depends(get_agent_service)` and returns `get_status()` as JSON.

```python
# src/api/routers/health.py — append if file exists, create if not
from fastapi import APIRouter, Depends

from src.services.agent_service import AgentService

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/agents")
async def get_agents_health(
    agent_svc: AgentService = Depends(get_agent_service),
) -> dict:
    status = await agent_svc.get_status()
    return {"success": True, "data": status}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → all passed

### Step 4: Register health router in `src/main.py`

TBD - 待验证：`src/main.py` 是否有现有的 `include_router` 调用 — 找到后在其附近添加：

```python
# src/main.py — find existing router includes and add health router
from src.api.routers.health import router as health_router

app.include_router(health_router)
```

**完成判定**：`ruff check src/main.py` → 0 errors

### Step 5: Write unit tests `tests/unit/test_agent_service.py`

Test the three behaviours:

1. `dispatch()` with a known agent type calls `registry.get()` and returns agent output.
2. `dispatch()` with an unknown agent type raises `NotFoundException`.
3. `get_status()` returns a dict containing `llm`, `agents`, and `timestamp` keys.

Mock `LLMService` and `AgentRegistry` using the pattern from `tests/unit/conftest.py`:

```python
# tests/unit/test_agent_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agent_service import AgentService
from src.pkg.errors.app_exceptions import NotFoundException


class TestAgentService:
    @pytest.fixture
    def mock_llm_service(self):
        svc = MagicMock()
        svc.health_check.return_value = True
        return svc

    @pytest.fixture
    def mock_registry(self):
        reg = MagicMock()
        return reg

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def agent_service(self, mock_session, mock_llm_service, mock_registry):
        return AgentService(mock_session, mock_llm_service, mock_registry)

    async def test_dispatch_success(self, agent_service, mock_registry):
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {"result": "ok"}
        mock_registry.get.return_value = mock_agent

        result = await agent_service.dispatch("greeting", {"text": "hi"}, tenant_id=1)
        assert result == {"result": "ok"}
        mock_registry.get.assert_called_once_with("greeting")

    async def test_dispatch_unknown_type_raises(self, agent_service, mock_registry):
        mock_registry.get.side_effect = KeyError("greeting")
        with pytest.raises(NotFoundException) as exc_info:
            await agent_service.dispatch("unknown", {"text": "hi"}, tenant_id=1)
        assert "unknown" in str(exc_info.value)

    async def test_get_status(self, agent_service):
        mock_agent = MagicMock()
        mock_agent.name = "greeting"
        agent_service._registry.list_types.return_value = ["greeting", "support"]

        status = await agent_service.get_status()
        assert status["llm"] == "ok"
        assert "greeting" in status["agents"]
        assert "timestamp" in status
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → 3 passed

---

## 6. 验收

- [ ] `ruff check src/services/agent_service.py src/api/deps.py src/api/routers/health.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_service.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_agent_service_integration.py -v` → all passed (only if the integration test file was created in this board)
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → N/A (no migrations in this board)
- [ ] End-to-end: `curl -s http://localhost:8000/health/agents | python -m json.tool` returns `{"success": true, "data": {"llm": "ok", "agents": [...], "timestamp": "..."}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `AgentRegistry.list_types()` method not present in `#627` delivery | 中 | 中 | Add a `list_types()` stub to `AgentRegistry` that returns `[]`; do not block on full agent registration list for health check |
| `AgentService` singleton holds stale `session` reference if `AsyncSession` is function-scoped in FastAPI | 低 | 高 | Make `get_agent_service` construct `AgentService` per-request by dropping the global singleton; performance impact is minimal for this board |
| `LLMService` constructor requires async config fetch that fails silently in unit tests | 低 | 中 | Mock `LLMService` entirely in unit tests; integration tests use a test API key env var |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/agent_service.py src/api/deps.py src/api/routers/health.py src/main.py tests/unit/test_agent_service.py
git commit -m "feat(automation): wire AgentService dispatch and FastAPI dependencies

- Add AgentService.dispatch() routing to AgentRegistry
- Add get_llm_service() and get_agent_service() to src/api/deps.py
- Add GET /health/agents endpoint
- Add unit tests for dispatch and status paths
Closes #628"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): wire AgentService dispatch and FastAPI dependencies" --body "Closes #628"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/api/deps.py` — existing dependency function pattern used throughout this repo
- 同类参考实现：`src/api/routers/` — existing router examples for health-check structure
- 父 issue / 关联：#41
- 依赖板块：#627

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
