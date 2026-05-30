# Agents Review · Add POST /agents/review and GET /agents/review/history routers

| 元数据 | 值 |
|---|---|
| Issue | #611 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [#610 新建模块](docs/dev-plan/00-foundations/) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #611 exposes the code-review capability to HTTP clients by wiring two API endpoints (`POST /agents/review`, `GET /agents/review/history`) to the `CodeReviewService` built in issue #610. Without these routers, the service exists but is unreachable — every consumer must bypass the HTTP layer and call the service directly, which skips auth middleware, session management, and the unified response envelope that the rest of the API guarantees.

### 1.2 做完后

- **用户视角**: Authenticated users can submit a code diff to `/agents/review` and receive a structured AI review. They can retrieve their review history via `/agents/review/history` (paginated). Unauthorized requests return HTTP 401 with `{"success": false, "message": "..."}`.
- **开发者视角**: Two new endpoints are registered under the `code_review` router tag. The `ai.py` router pattern is directly replicated: session injected via `Depends(get_db)`, auth via `Depends(require_auth)`, results serialized with `.to_dict()` and wrapped in `{"success": true, "data": ..., "message": "..."}`. No try/catch — `AppException` subclasses propagate to the global handler in `main.py`.

### 1.3 不做什么（剔除）

- [ ] No service-layer implementation — `CodeReviewService` is assumed to exist from issue #610; this board only adds the router layer.
- [ ] No database schema changes — `CodeReviewService` owns any ORM models; routers do not create or alter tables.
- [ ] No background task / queue integration — `POST /agents/review` returns synchronously; async review execution (if any) is internal to `CodeReviewService`.

### 1.4 关键 KPI

- `ruff check src/api/routers/code_review.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → ≥ 3 passed (happy path, 401-without-auth, bad-request shape)
- `curl -X POST http://localhost:8000/api/v1/agents/review -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"diff":"..."}'` → HTTP 200, `{"success": true, "data": {...}}`
- `curl http://localhost:8000/api/v1/agents/review/history` without auth → HTTP 401

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：确认 `src/services/code_review_service.py` 存在并记录 `CodeReviewService` 的方法签名。预期结构：

主入口：`src/api/routers/ai.py` L73-L108（现有 AI router 模式，直接复用）

```python
@ai_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    _check_rate_limit(ctx.tenant_id, ctx.user_id)
    svc = AIService(session)
    result = await svc.send_message(...)
    return _success(result.to_dict(), message=result.reply or "")
```

路由发现：`src/api/__init__.py` L19-L26 — 所有 `src/api/routers/` 下的 `APIRouter` 实例通过 `iter_routers()` 自动被 `main.py` 纳入，无需改动 `main.py`。

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/code_review.py` — 新建，定义两个 endpoint
  - `tests/unit/test_code_review.py` — 新建，单元测试
- 要建：
  - `src/services/code_review_service.py` — 由 #610 产出，非本板块范围；本板块依赖它存在
  - `src/models/code_review.py` — 由 #610 产出，Pydantic 请求/响应模型

### 2.3 缺什么

- [ ] `POST /agents/review` endpoint: receives code-diff payload, calls `CodeReviewService.submit_review()`, returns `{"success": true, "data": <ORM-object.to_dict()>}`.
- [ ] `GET /agents/review/history` endpoint: calls `CodeReviewService.list_reviews(tenant_id=ctx.tenant_id, ...)`, returns paginated list.
- [ ] Pydantic request schema (`CodeReviewRequest`) and response schema (`CodeReviewResponse`) in `src/models/code_review.py`.
- [ ] Unit tests covering: happy path, missing auth (401), malformed request body (422).

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/code_review.py` | 两个 FastAPI endpoint：POST /agents/review，GET /agents/review/history |
| `src/models/code_review.py` | `CodeReviewRequest` / `CodeReviewResponse` Pydantic 模型 |
| `tests/unit/test_code_review.py` | 单元测试（mock `CodeReviewService`，mock `require_auth`） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/api/__init__.py` | 无需改动 — `iter_routers()` 自动发现新 router |
| `src/main.py` | 无需改动 — 同上 |

### 3.3 新增能力

- **API endpoint**：`POST /api/v1/agents/review` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /api/v1/agents/review/history` → `{"success": true, "data": {"items": [...], "total": N, ...}}`
- **Pydantic schema**：`CodeReviewRequest`（`diff: str`，可选 `language: str`）
- **Pydantic schema**：`CodeReviewResponse` / `PaginatedCodeReviewHistory`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **沿用 `ai.py` 的 dict-envelope 模式，不复用 `ApiResponse` Pydantic class**：现有 `ai.py`、`sales.py` 等 router 全部返回 `{"success": true, "data": ..., "message": "..."}` dict；`ApiResponse`（`models/response.py`）虽存在但未被 router 层使用。保持一致避免两种响应格式共存。
- **沿用 `Depends(get_db)` 而非 `async with get_db()`**：项目强制规则，CLAUDE.md §Router Pattern 明确禁止 `async with` 模式。
- **Session 注入在路由层，不在 service 层**：router 持有 `AsyncSession`，传给 `CodeReviewService(session)`，service 不自行获取 session。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：每个 service 调用必须传 `tenant_id=ctx.tenant_id`（来自 `AuthContext`）。
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责。
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`。
- Router 不写 try/except — 全局 `AppException` handler 兜底（`main.py` L62-L68）。

### 4.4 已知坑

1. **Pydantic schema 列名与 ORM 模型列名不一致** → 规避：router 层直接调用 `.to_dict()`，不经过 Pydantic validation 做字段映射。
2. **`Depends(get_db)` 在测试里需要 mock** → 规避：单元测试使用 `tests/unit/conftest.py` 的 `make_mock_session`，路由测试通过 `TestClient` 或直接调用 async handler function with patched dependencies.

---

## 5. 实现步骤（按顺序）

### Step 1: 定义 Pydantic 请求/响应模型

在 `src/models/code_review.py` 中新增：

```python
"""Code review request/response schemas."""
from pydantic import BaseModel, Field


class CodeReviewRequest(BaseModel):
    diff: str = Field(..., min_length=1, description="Unified diff or raw file content")
    language: str | None = Field(None, description="Programming language hint, e.g. 'python'")


class CodeReviewResult(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    diff: str
    language: str | None
    result: str  # AI review text
    created_at: str  # ISO8601


class CodeReviewHistoryResponse(BaseModel):
    items: list[CodeReviewResult]
    total: int
    page: int
    page_size: int
    total_pages: int
```

**完成判定**：`ruff check src/models/code_review.py` → 0 errors

---

### Step 2: 编写路由处理器骨架

在 `src/api/routers/code_review.py` 中：

```python
"""Agents code-review router — /api/v1/agents/review, /api/v1/agents/review/history."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.code_review import CodeReviewRequest, CodeReviewHistoryResponse
from services.code_review_service import CodeReviewService

code_review_router = APIRouter(prefix="/api/v1/agents", tags=["code_review"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}


def _paginated(items: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }
```

**完成判定**：`ruff check src/api/routers/code_review.py` → 0 errors（骨架阶段）

---

### Step 3: 实现 POST /agents/review 端点

在 `code_review_router` 实例后追加：

```python
@code_review_router.post("/review")
async def submit_review(
    request: CodeReviewRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = CodeReviewService(session)
    review = await svc.submit_review(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        diff=request.diff,
        language=request.language,
    )
    return _success(review.to_dict())
```

**完成判定**：`ruff check src/api/routers/code_review.py` → 0 errors

---

### Step 4: 实现 GET /agents/review/history 端点

在 `code_review_router` 中追加：

```python
@code_review_router.get("/review/history")
async def get_review_history(
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = CodeReviewService(session)
    reviews, total = await svc.list_reviews(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        page=page,
        page_size=page_size,
    )
    items = [r.to_dict() for r in reviews]
    return _paginated(items, total, page, page_size)
```

**完成判定**：`ruff check src/api/routers/code_review.py` → 0 errors

---

### Step 5: 编写单元测试

在 `tests/unit/test_code_review.py` 中使用 `tests/unit/conftest.py` 的 mock 基础设施：

```python
"""Unit tests for code_review router."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.code_review import code_review_router, submit_review, get_review_history
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth


class MockReview:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


@pytest.fixture
def mock_session():
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def mock_ctx():
    return AuthContext(tenant_id=1, user_id=1)


@pytest.mark.asyncio
async def test_submit_review_happy_path(mock_session, mock_ctx):
    from services import code_review_service
    original = getattr(code_review_service, "CodeReviewService", None)

    mock_svc = AsyncMock()
    mock_svc.submit_review = AsyncMock(
        return_value=MockReview(id=1, tenant_id=1, user_id=1, diff="foo", language="py", result="OK")
    )

    class FakeSvc:
        def __init__(self, session):
            pass

    # Patch CodeReviewService
    code_review_service.CodeReviewService = lambda session: mock_svc

    async def override_require_auth():
        return mock_ctx

    async def override_get_db():
        yield mock_session

    app = code_review_router
    app.dependency_overrides[require_auth] = override_require_auth
    app.dependency_overrides[get_db] = override_get_db

    from models.code_review import CodeReviewRequest
    result = await submit_review(
        request=CodeReviewRequest(diff="foo", language="py"),
        ctx=mock_ctx,
        session=mock_session,
    )

    assert result["success"] is True
    assert result["data"]["id"] == 1

    if original:
        code_review_service.CodeReviewService = original
    else:
        delattr(code_review_service, "CodeReviewService")
    app.dependency_overrides.clear()
```

至少再增加两个测试用例：

- `test_submit_review_missing_auth`：不注入 `require_auth` override，直接 call `submit_review`，期望 `ForbiddenException` 或路由层 401。
- `test_get_review_history_paginated`：mock `svc.list_reviews` 返回空列表，验证 `_paginated` 输出的 `total`、`total_pages` 字段存在且正确。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/code_review.py src/models/code_review.py` → 0 errors
- [ ] `ruff check tests/unit/test_code_review.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src python -c "from api.routers.code_review import code_review_router; print('import ok')"` → `import ok`
- [ ] 端到端（需 `CodeReviewService` 存在）：`curl -X POST http://localhost:8000/api/v1/agents/review -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"diff":"def foo(): pass","language":"python"}'` → HTTP 200，`"success": true`
- [ ] 无认证请求 → HTTP 401，`"success": false`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#610` `CodeReviewService` 方法签名与本板块假设不符（参数名/返回类型） | 中 | 中 | 调整 router 调用参数匹配实际签名；不影响其他已注册 router |
| `iter_routers()` 未发现新 router（文件命名或 export 不正确） | 低 | 高 | 确认 `src/api/routers/code_review.py` 导出 `code_review_router: APIRouter`，`iter_routers()` 自动含之 |
| Pydantic schema 与 ORM `.to_dict()` 字段名不一致导致 client 拿到意外 null | 低 | 低 | router 直接透传 `.to_dict()` 结果；若字段缺失，在 `CodeReviewService` 层面修复 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/code_review.py src/models/code_review.py tests/unit/test_code_review.py
git commit -m "feat(agents): add POST /agents/review and GET /agents/review/history routers"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(agents): routers for code-review (#611)" --body "Closes #611

## Summary
- POST /api/v1/agents/review — submit a code diff for AI review
- GET /api/v1/agents/review/history — paginated review history

## Test plan
- [ ] ruff check src/api/routers/code_review.py src/models/code_review.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_code_review.py -v → ≥ 3 passed
- [ ] curl POST /agents/review with auth → 200 success
- [ ] curl GET /agents/review/history without auth → 401"

# 2. 更新进度
# 本板块文档 docs/dev-plan/70-platform/0611-add-post-agents-review-and-get-agents-review-history-routers.md 状态改为 ✅ 已完成
# PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现（路由模式）：[`src/api/routers/ai.py`](../../../src/api/routers/ai.py)
- 同类参考实现（服务模式）：[`src/services/ai_service.py`](../../../src/services/ai_service.py)
- 响应包装参考：[`src/models/response.py`](../../../src/models/response.py) L1-L176
- 路由自动发现机制：[`src/api/__init__.py`](../../../src/api/__init__.py) L19-L26
- 全局异常处理：[`src/main.py`](../../../src/main.py) L62-L84
- 父 issue / 关联：#44, #610

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
