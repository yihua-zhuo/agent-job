# AI Draft · POST /ai/draft router endpoint

| 元数据 | 值 |
|---|---|
| Issue | #578 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [#577](../50-automation/0577-add-aidraft-pydantic-schemas-and-aidraftservice.md) |
| 启用后赋能 | 前端 AI Draft 表单（待后续板块） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #577 adds `AiDraftService` and the `DraftResponse` Pydantic model. The service is ready but has no HTTP entry point — POST requests to `/ai/draft` return 404. Without a router endpoint, no frontend or external client can invoke the AI draft generation capability, blocking downstream frontend work.

### 1.2 做完后

- **用户视角**：无用户可见变化 — this is pure backend wiring.
- **开发者视角**：`POST /ai/draft` becomes available as a typed HTTP endpoint. Consumers can send `{ "prompt": "...", "..." }` and receive `{"success": true, "data": DraftResponse.to_dict()}`. The endpoint enforces auth and multi-tenancy via `AuthContext`.

### 1.3 不做什么（剔除）

- [ ] Implement `AiDraftService` — done in #577, not here.
- [ ] Add frontend form or UI for the draft feature.
- [ ] Add GET /ai/draft or any other HTTP verb for drafts.
- [ ] Add integration tests beyond unit coverage for the router.

### 1.4 关键 KPI

- [Router file `src/api/routers/ai_draft.py` exists and contains a `POST /ai/draft` route]
- [`ruff check src/api/routers/ai_draft.py src/main.py` → 0 errors]
- [`PYTHONPATH=src pytest tests/unit/test_ai_draft.py -v` → all passed]
- [Router wired in `src/main.py` and reachable at `/ai/draft` after server start]

---

## 2. 当前现状（起点）

### 2.1 现有实现

`AiDraftService` and `DraftResponse` are expected to be added by #577.

TBD — 待验证：`src/services/ai_draft_service.py` 或 `src/services/draft_service.py` — 应由 #577 创建，尚未确认具体路径

TBD — 待验证：`src/models/response.py` 中的 `DraftResponse` schema — 应由 #577 创建

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — 挂载 `ai_draft` router 到 `/ai/draft` 路径前缀
- 要建：
  - `src/api/routers/ai_draft.py` — POST endpoint 调用 `AiDraftService`
  - `tests/unit/test_ai_draft.py` — 路由层单元测试（mock session + auth context）

### 2.3 缺什么

- [ ] `POST /ai/draft` endpoint — 404 today, needed to wire the service from #577]
- [ ] Router wired into FastAPI app in `src/main.py`
- [ ] Unit test for the router path (coverage of happy path + auth rejection)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/api/routers/ai_draft.py` | FastAPI router: `POST /ai/draft` → injects session + AuthContext → calls `AiDraftService` → returns `ApiResponse` envelope |
| `tests/unit/test_ai_draft.py` | Unit tests: mock session, `require_auth` dep, assert response envelope shape |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | `app.include_router(ai_draft.router, prefix="/ai", tags=["AI"])` — 挂载 ai_draft router |

### 3.3 新增能力

- **API endpoint**：`POST /ai/draft` — authenticated, multi-tenant, JSON body `{...}`, returns `{"success": true, "data": DraftResponse.to_dict()}`
- **Router module**：`src/api/routers/ai_draft.py` — follows existing router pattern (session via `Depends(get_db)`, auth via `AuthContext = Depends(require_auth)`)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Follow existing router pattern** rather than inventing a new one: inject `session: AsyncSession = Depends(get_db)` and `ctx: AuthContext = Depends(require_auth)`. This is consistent with every other router in `src/api/routers/` and makes the auth + multi-tenancy guarantees uniform.

### 4.2 版本约束

<!-- 无新依赖引入，整段删掉 -->

### 4.3 兼容性约束

- 多租户：router passes `tenant_id=ctx.tenant_id` to every service call.
- Session injection: `session: AsyncSession = Depends(get_db)` — **never** `async with get_db()`.
- Service errors raise `AppException` subclasses — global handler in `main.py` converts them; no try/catch in router.
- Serialization: router calls `DraftResponse.to_dict()` before putting result into `ApiResponse` envelope — **never** call `.to_dict()` inside a service.
- Import paths: always `from services...`, `from models...`, `from db.connection import get_db` — **never** `from src.services...`.

### 4.4 已知坑

1. **Router registered before service is ready** — if #577 is not merged, `from services.ai_draft_service import AiDraftService` will raise `ImportError`. Execution order matters: #577 must merge before this board starts. No workaround; gate behind dependency.
2. **Auth context mock in tests** — `require_auth` is a FastAPI `Depends`. In unit tests, mock it with a `fixture` that returns a hardcoded `AuthContext(tenant_id=1, user_id=1)` so the router dependency graph is satisfied without spinning up the full auth middleware.

---

## 5. 实现步骤（按顺序）

### Step 1: Create src/api/routers/ai_draft.py

Create the router file. Follow the established pattern used by other routers in this repo (e.g. `src/api/routers/customers.py` or `src/api/routers/tickets.py`). Import `AiDraftService` from the path confirmed by #577.

```python
# src/api/routers/ai_draft.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ApiResponse, DraftResponse
from services.ai_draft_service import AiDraftService  # type: ignore[attr-defined] # from #577

router = APIRouter(prefix="/draft", tags=["AI"])

@router.post("")
async def create_draft(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AiDraftService(session)
    draft = await svc.create_draft(tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    return ApiResponse(success=True, data=draft.to_dict()).model_dump()
```

**完成判定**：`ruff check src/api/routers/ai_draft.py` → 0 errors

---

### Step 2: Wire router into src/main.py

TBD — 待验证：在 `src/main.py` 的 router 导入区查找 `include_router` 调用模式，然后在合适位置添加 `app.include_router(ai_draft.router, prefix="/ai", tags=["AI"])`。

具体操作：在 `src/main.py` 中添加 `from api.routers import ai_draft` 并在 `app.include_router(...)` 调用链中注册。

**完成判定**：`ruff check src/main.py` → 0 errors

---

### Step 3: Write unit test tests/unit/test_ai_draft.py

Test the router path with a mock session and a mocked `AuthContext` fixture. Verify:
- Authenticated request returns `{success: True, data: {...}}`.
- Unauthenticated request (mock `require_auth` raises) returns 401.

```python
# tests/unit/test_ai_draft.py
import pytest
from unittest.mock import AsyncMock

from api.routers.ai_draft import router
from internal.middleware.fastapi_auth import AuthContext
from services.ai_draft_service import AiDraftService
from models.ai_draft import DraftResponse  # type: ignore

@pytest.fixture
def fake_auth():
    return AuthContext(tenant_id=1, user_id=42)

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def mock_ai_draft_service(mock_session, monkeypatch):
    svc = AsyncMock(spec=AiDraftService)
    draft = DraftResponse(id=1, content="test draft", created_by=42)
    svc.create_draft.return_value = draft
    monkeypatch.setattr("api.routers.ai_draft.AiDraftService", lambda _: svc)
    return svc

def test_create_draft_success(fake_auth, mock_session, mock_ai_draft_service):
    # call router logic directly or via TestClient
    pass

def test_create_draft_unauthenticated():
    pass
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_draft.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/ai_draft.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_draft.py -v` → all passed
- [ ] Import check — `python -c "from api.routers.ai_draft import router"` exit 0
- [ ] `PYTHONPATH=src mypy src/api/routers/ai_draft.py` → 0 errors (type-correct router)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #577 not merged before this work starts — `AiDraftService` import fails | 低 | 高（blocker） | Wait for #577 to merge; rebase this branch before implementing |
| Service method signature in #577 differs from what router expects | 低 | 中 | Adjust router call signature to match actual `AiDraftService.create_draft(...)` signature |
| Router path conflicts with existing `/ai/draft` in future auth middleware | 低 | 中 | Rename prefix to `/ai/v1/draft` — minimal change, no downstream impact |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/ai_draft.py src/main.py tests/unit/test_ai_draft.py
git commit -m "feat(ai): add POST /ai/draft router endpoint

wire AiDraftService behind POST /ai/draft with auth context and
multi-tenant tenant_id injection.

closes #578"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ai): POST /ai/draft router endpoint" --body "Closes #578"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 标准的 router + service + auth pattern
- 同类参考实现：[`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) — 另一个 CRUD router 参考
- 父 issue / 关联：#50
- 前置依赖：#577

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
