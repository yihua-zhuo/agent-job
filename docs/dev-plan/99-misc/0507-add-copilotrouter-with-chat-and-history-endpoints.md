# CopilotRouter · Add chat and history endpoints

| 元数据 | 值 |
|---|---|
| Issue | #507 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [「平台基础服务层」](../00-foundations/README.md) |
| 启用后赋能 | [「任务自动化规则引擎」](../50-automation/README.md), [「客户 AI 助手」](../30-tickets/README.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM needs a structured API surface for AI-powered copilot interactions. Issue #506 provides the underlying `CopilotService` that handles message routing and AI tool-call dispatch; this board adds the HTTP endpoints that expose those capabilities to clients. Without a router, the service exists but is unreachable.

### 1.2 做完后

- **用户视角**：Clients can send a message to the copilot via `POST /copilot/chat` and retrieve conversation context via `GET /copilot/{conversation_id}/history`. Both return a consistent `{"success": true, "data": ...}` envelope.
- **开发者视角**：The codebase gains `src/api/routers/copilot.py` with two new endpoints wired into the FastAPI app. Unit and integration test coverage confirms the endpoints register and return the expected shape.

### 1.3 不做什么（剔除）

- [ ] AI logic / LLM integration — handled in the `CopilotService` from issue #506
- [ ] WebSocket / streaming endpoint — not in scope for this board
- [ ] Authentication implementation — `require_auth` is already wired; this board uses it as-is

### 1.4 关键 KPI

- [ ] `ruff check src/api/routers/copilot.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → all passed (when written)
- [ ] `PYTHONPATH=src pytest tests/integration/test_copilot_integration.py -v` → all passed
- [ ] App starts with `uvicorn src.main:app` and `/copilot/chat`, `/copilot/{id}/history` registered

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — register `CopilotRouter` in the FastAPI app
- 要建：
  - `src/api/routers/copilot.py` — `CopilotRouter` with two endpoints
  - `tests/unit/test_copilot.py` — unit tests for the router
  - `tests/integration/test_copilot_integration.py` — integration tests against real DB

### 2.3 缺什么

- [ ] `CopilotRouter` registered in the app — endpoints unreachable
- [ ] `POST /copilot/chat` endpoint — clients have no way to send messages
- [ ] `GET /copilot/{conversation_id}/history` endpoint — no conversation recall
- [ ] Unit tests for the new router
- [ ] Integration tests confirming end-to-end correctness

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/copilot.py` | `CopilotRouter` — `POST /copilot/chat` and `GET /copilot/{conversation_id}/history` |
| `tests/unit/test_copilot.py` | Unit tests for `CopilotRouter` endpoints |
| `tests/integration/test_copilot_integration.py` | Integration tests with real PostgreSQL via docker compose |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | Import and register `CopilotRouter` with `app.include_router(copilot_router)` |

### 3.3 新增能力

- **API endpoint**：`POST /copilot/chat` → `{"success": true, "data": {"response": "...", "tool_calls": [...]}}`
- **API endpoint**：`GET /copilot/{conversation_id}/history` → `{"success": true, "data": {"messages": [...], "total": N}}` (max 20, most recent first)
- **Router**：`CopilotRouter` in `src/api/routers/copilot.py`
- **Integration test**：`tests/integration/test_copilot_integration.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use `CopilotService` from issue #506 rather than duplicating logic in the router** — the service encapsulates all business logic; the router only handles HTTP serialization and the `{"success": true, "data": ...}` envelope.
- **Return last 20 messages on history** — simple LIMIT clause, no cursor/pagination for v1. Cursor pagination can be added in a follow-up board if needed.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `fastapi` | `≥0.115` | Required for current app version |
| `sqlalchemy` | `2.x` | Async SQLAlchemy used throughout |
| `pytest` | `≥8` | Test runner |

### 4.3 兼容性约束

- Auth: every endpoint must use `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`
- Envelope: `{"success": true, "data": ...}` — never return a raw object at top level
- Errors: do NOT wrap logic in try/except; raise `AppException` subclasses and let the global handler in `main.py` convert them
- Multi-tenancy: every SQL query must filter by `tenant_id = ctx.tenant_id`
- Service: `CopilotService(session)` — no default for `session`; service returns ORM objects, router calls `.to_dict()`

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()`** → If a migration is added later for a copilot table, manually change `JSON()` to `JSONB()` and add `Timezone=True` to any datetime columns autogen wrote as `DateTime(timezone=False)`
2. **Router import order / circular imports** → Keep `CopilotService` import inside the router file; do not import from `main.py` into the router

---

## 5. 实现步骤（按顺序）

### Step 1: Create CopilotRouter skeleton

Create `src/api/routers/copilot.py` with the router definition and stub endpoints that return `{}` placeholders. Wire it into `src/main.py` so the routes are visible in the OpenAPI schema at `/docs`.

操作：
- a) Write `src/api/routers/copilot.py` with empty endpoint handlers
- b) Import and register in `src/main.py`: `app.include_router(copilot_router, prefix="/copilot", tags=["Copilot"])`

示例代码：

```python
# src/api/routers/copilot.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/chat")
async def chat(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return {"success": True, "data": {}}


@router.get("/{conversation_id}/history")
async def history(
    conversation_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return {"success": True, "data": {"messages": [], "total": 0}}
```

**完成判定**：`ruff check src/api/routers/copilot.py` exit 0 / `ruff check src/main.py` exit 0

---

### Step 2: Wire CopilotService into chat endpoint

Replace the stub in `POST /copilot/chat` with a real call to `CopilotService`. Use the issue #506 service. Return the AI text and tool_calls list in the data envelope.

操作：
- a) `from services.copilot_service import CopilotService` at top of `copilot.py`
- b) Replace the chat handler body with service call + `.to_dict()` serialization

示例代码：

```python
@router.post("/chat")
async def chat(
    message: str,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CopilotService(session)
    result = await svc.send_message(message, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}
```

**完成判定**：`ruff check src/api/routers/copilot.py` exit 0 / `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → passed

---

### Step 3: Wire CopilotService into history endpoint

Replace the stub in `GET /copilot/{conversation_id}/history` with a real call that fetches messages and slices the last 20. Return `{"messages": [...], "total": N}`.

操作：
- a) Replace the history handler body with service call, apply `[:20]` slice, serialize

示例代码：

```python
@router.get("/{conversation_id}/history")
async def history(
    conversation_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CopilotService(session)
    messages = await svc.get_history(conversation_id, tenant_id=ctx.tenant_id)
    sliced = messages[:20]
    return {
        "success": True,
        "data": {
            "messages": [m.to_dict() for m in sliced],
            "total": len(sliced),
        },
    }
```

**完成判定**：`ruff check src/api/routers/copilot.py` exit 0 / `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → passed

---

### Step 4: Write unit tests

Create `tests/unit/test_copilot.py` with mocked `CopilotService`. Test that the envelope is `{"success": True, ...}` and that history caps at 20 messages.

操作：
- a) Define `mock_db_session` fixture using `make_mock_session` from `conftest.py`
- b) Write `test_chat_returns_envelope`, `test_history_returns_envelope`, `test_history_caps_at_20`

示例代码：

```python
# tests/unit/test_copilot.py
import pytest
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
from src.main import app
from tests.unit.conftest import make_mock_session, MockState


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
async def client(mock_db_session):
    from src.db.connection import get_db
    app.dependency_overrides[get_db] = lambda: mock_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_returns_envelope(client, mocker):
    mocker.patch(
        "services.copilot_service.CopilotService.send_message",
        new_callable=AsyncMock,
        return_value={"response": "hi", "tool_calls": []},
    )
    res = await client.post("/copilot/chat?message=hello")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "data" in data
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → all passed

---

### Step 5: Write integration tests

Create `tests/integration/test_copilot_integration.py`. Use the `db_schema`, `tenant_id`, and `async_session` fixtures. Seed a conversation and two messages, call both endpoints, assert response shape and history cap.

操作：
- a) Create `tests/integration/test_copilot_integration.py`
- b) Add `test_chat_integration`, `test_history_integration`, `test_history_caps_at_20`

示例代码：

```python
# tests/integration/test_copilot_integration.py
import pytest

from tests.integration.conftest import _seed_conversation, _seed_message


@pytest.mark.integration
class TestCopilotIntegration:
    async def test_chat_integration(self, db_schema, tenant_id, async_session):
        from src.api.routers.copilot import router
        from src.services.copilot_service import CopilotService
        svc = CopilotService(async_session)
        # assumes _seed_conversation helper exists
        conv = await _seed_conversation(async_session, tenant_id)
        result = await svc.send_message("hello", conversation_id=conv.id, tenant_id=tenant_id)
        assert result is not None

    async def test_history_caps_at_20(self, db_schema, tenant_id, async_session):
        from src.services.copilot_service import CopilotService
        svc = CopilotService(async_session)
        conv = await _seed_conversation(async_session, tenant_id)
        for i in range(25):
            await _seed_message(async_session, conv.id, tenant_id, f"msg {i}")
        history = await svc.get_history(conv.id, tenant_id=tenant_id)
        assert len(history) == 20
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_copilot_integration.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/copilot.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_copilot_integration.py -v` → all passed
- [ ] App starts: `uvicorn src.main:app` exits 0 (no import errors)
- [ ] OpenAPI schema at `http://localhost:8000/openapi.json` contains `POST /copilot/chat` and `GET /copilot/{conversation_id}/history`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `CopilotService` from issue #506 is delayed or changes interface | 中 | 高 | Define a local stub service class in `copilot.py` for the router until #506 lands; swap in the real service via a later patch |
| Circular import when importing `CopilotService` in `copilot.py` | 低 | 中 | Move import inside the handler function body; do not import at module top |
| History cap `[:20]` leaks partial state if DB returns fewer than 20 messages | 低 | 低 | Cap is a no-op on short result sets — no data loss possible |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/copilot.py src/main.py tests/unit/test_copilot.py tests/integration/test_copilot_integration.py
git commit -m "feat(copilot): add POST /copilot/chat and GET /copilot/{id}/history endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(copilot): router with chat and history endpoints" --body "Closes #507"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) — same envelope pattern, `AuthContext`, `AsyncSession` injection
- 父 issue / 关联：#76
- 前置依赖：#506

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
