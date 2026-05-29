# 中间件 · 实现 TenantMiddleware 与 require_tenant 依赖

| 元数据 | 值 |
|---|---|
| Issue | #473 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [实现 TenantContext 工具类](../99-misc/0472-implement-tenant-context-utilities.md) |
| 启用后赋能 | [审计 tenant_id 过滤](../99-misc/0488-audit-tenant-id-filtering-across-activityservice.md), [实现 DataIsolationService](../70-platform/0475-implement-dataisolationservice-and-isolation-integration-tes.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Multi-tenant CRM requires that every data access query filter by `tenant_id`. Without a centralized middleware layer that establishes and propagates tenant context, individual service methods must each validate and extract the tenant — a responsibility that is error-prone and duplicates logic across every router and service. Issue #472 establishes the `TenantContext` utility; this板块 wires that context into the FastAPI request lifecycle as middleware, providing a reusable `require_tenant` guard so that routes can enforce tenant presence without ad-hoc checks.

### 1.2 做完后

- **用户视角**：无用户可见 changes — 纯底层 enforcement layer.
- **开发者视角**：
  - Any router handler can inject `require_tenant` (or use `get_tenant_id` / `set_tenant_id`) to work with the current tenant without duplicating extraction logic.
  - `filter_by_tenant(query, table)` is available for SQLAlchemy query injection so that manual `WHERE tenant_id = :tenant_id` clauses are consistent and DRY.
  - Unauthenticated or cross-tenant requests raise `UnauthorizedException` automatically via the middleware pipeline, eliminating silent tenant-id None bugs.

### 1.3 不做什么（剔除）

- [ ] Authentication / JWT token parsing — that is handled by the existing `require_auth` / `AuthContext` in `src/internal/middleware/fastapi_auth.py`. TenantMiddleware reads tenant_id from the `AuthContext` already established by auth middleware; it does NOT re-implement token logic.
- [ ] Row-level security or column-level encryption — this is an application-level enforcement only.
- [ ] Multi-tenancy by schema (postgres `search_path`) — we enforce at the ORM query level only.
- [ ] New database migration — TenantMiddleware is pure Python; no new tables or columns required.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_tenant_middleware.py -v` → ≥ 5 passed
- `ruff check src/internal/middleware/tenant_middleware.py src/main.py` → 0 errors
- `PYTHONPATH=src mypy src/internal/middleware/tenant_middleware.py` → 0 errors
- All three scenarios from unit tests pass: no-tenant raises `UnauthorizedException`, valid tenant allows through, cross-tenant blocked by mock service.

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — [在 app middleware 栈中注册 `TenantMiddleware`；read tenant_id from `request.state.auth_context`]
  - TBD - 待验证：`src/internal/middleware/fastapi_auth.py` L? — 现有 `require_auth` / `AuthContext`; TenantMiddleware reads from its `state.tenant_id`
- 要建：
  - `src/internal/middleware/tenant_middleware.py` — [TenantMiddleware class with `set_tenant_id`, `get_tenant_id`, `require_tenant`, `filter_by_tenant`]
  - `tests/unit/test_tenant_middleware.py` — [Unit tests: test_middleware_requires_tenant, test_middleware_allows_valid_tenant, test_cross_tenant_blocked]
  - TBD - 待验证：`src/internal/middleware/__init__.py` — [exports TenantMiddleware; may need to add if `__init__.py` does not already exist]

### 2.3 缺什么

- [ ] No centralized `TenantMiddleware` that reads `AuthContext.tenant_id` and stores it in request state — individual routes extract it ad-hoc.
- [ ] No `require_tenant` guard callable from route handlers to abort with `UnauthorizedException` when tenant context is absent.
- [ ] No `filter_by_tenant` helper for consistent `WHERE tenant_id = :tenant_id` injection in raw SQL or ORM queries.
- [ ] `src/main.py` has no tenant-aware middleware registered — the app-level middleware chain only includes auth and CORS today.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/internal/middleware/tenant_middleware.py` | TenantMiddleware: set_tenant_id, get_tenant_id, require_tenant, filter_by_tenant |
| `tests/unit/test_tenant_middleware.py` | Unit tests covering no-tenant, valid-tenant, and cross-tenant scenarios |
| `src/internal/middleware/__init__.py` | Exports `TenantMiddleware` (add if not already present) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | Register `TenantMiddleware` in app middleware stack; read `tenant_id` from `request.state.auth_context.tenant_id` |

### 3.3 新增能力

- **Python class**：`TenantMiddleware` in `src/internal/middleware/tenant_middleware.py`
  - `set_tenant_id(tenant_id: int)` → stores in `request.state.tenant_id`
  - `get_tenant_id() -> int` → reads from `request.state`, raises `UnauthorizedException` if absent
  - `require_tenant()` → alias raising UnauthorizedException; used as a FastAPI dependency or called at route entry
  - `filter_by_tenant(query, table)` → returns query with `WHERE tenant_id = :tenant_id` injected
- **Unit tests**：3 test functions in `tests/unit/test_tenant_middleware.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 TenantMiddleware (ASGI middleware) 而不选 per-router decorator**：FastAPI middleware runs once per request before any route handler, so `set_tenant_id` is guaranteed to be called before any service method executes. A decorator approach would require every router to opt-in manually and would not catch direct service calls. ASGI middleware is the canonical FastAPI pattern for cross-cutting concerns.
- **选 `require_tenant` as a standalone callable / FastAPI Depends, not as a decorator wrapping each route**：Keeping it as a plain function that raises `UnauthorizedException` means it works both as a `Depends()` dependency in individual routes AND can be called manually inside a route body. A decorator would be more verbose and is unnecessary for this use case.
- **选 `filter_by_tenant` that accepts (query, table_name) instead of a global query rewriter**：Explicit `(query, table)` arguments make the call site self-documenting and avoid subtle bugs where a shared `Query` object gets mutated across service calls. The caller passes `select(T).where(T.c.tenant_id == tenant_id)` explicitly.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `starlette` | `>=0.27` | TenantMiddleware inherits from `starlette.middleware.base.BaseHTTPMiddleware`; available in all versions bundled with FastAPI 0.100+ |

### 4.3 兼容性约束

- `TenantMiddleware` must be registered **after** auth middleware in the app middleware chain — it reads `request.state.auth_context.tenant_id` set by the auth middleware.
- `get_tenant_id` raises `UnauthorizedException` (from `pkg/errors/app_exceptions.py`), which is caught by the global exception handler in `main.py` and returned as HTTP 401. Do NOT return a dict or raise a raw `Exception`.
- `filter_by_tenant` must use SQLAlchemy `select()` / `update()` / `delete()` APIs with explicit `where()` clauses — do not use raw string concatenation.
- All methods are async to match FastAPI's ASGI contract.

### 4.4 已知坑

1. **Starlette `BaseHTTPMiddleware` dispatches via `self.dispatch` which is not a plain coroutine — calling `await self.app(scope, receive, send)` directly from inside a middleware method can cause double-execution in some Starlette versions** →规避：`super().dispatch(call_next)` is the only correct way to call the next layer; do not replace it with `await self.app(...)`.
2. **PYTHONPATH=src, import `UnauthorizedException` as `from pkg.errors.app_exceptions import UnauthorizedException`** → 规避：use the full package path as per CLAUDE.md conventions; `from src.internal.middleware` imports will not resolve without `src` in PYTHONPATH.
3. **Alembic autogenerate is not involved here** → no migration needed, so the JSON vs JSONB / timezone=True caveats from CLAUDE.md §Alembic do not apply to this板块.

---

## 5. 实现步骤（按顺序）

### Step 1: Create src/internal/middleware/tenant_middleware.py

Create the file with the `TenantMiddleware` class. The middleware reads `tenant_id` from `request.state.auth_context.tenant_id` (set by upstream auth middleware) and stores it in `request.state.tenant_id`. Expose `set_tenant_id`, `get_tenant_id`, `require_tenant`, and `filter_by_tenant` as module-level utilities so they can be imported by routers and services.

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.sql import Select

from pkg.errors.app_exceptions import UnauthorizedException

_tenant_context: dict[int, int] = {}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_context = getattr(request.state, "auth_context", None)
        if auth_context and hasattr(auth_context, "tenant_id"):
            request.state.tenant_id = auth_context.tenant_id
            _tenant_context[id(request)] = auth_context.tenant_id
        response = await call_next(request)
        _tenant_context.pop(id(request), None)
        return response


def set_tenant_id(request: Request, tenant_id: int) -> None:
    request.state.tenant_id = tenant_id


def get_tenant_id(request: Request) -> int:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise UnauthorizedException("Tenant context required")
    return tenant_id


def require_tenant(request: Request) -> int:
    return get_tenant_id(request)


def filter_by_tenant(query: Select, tenant_id: int) -> Select:
    from sqlalchemy import inspect
    from src.db.base import Base
    for table in Base.metadata.tables.values():
        if query.is_derived_from(table):
            return query.where(table.c.tenant_id == tenant_id)
    raise ValidationException("Cannot determine tenant table from query")
```

**完成判定**：`ruff check src/internal/middleware/tenant_middleware.py` → 0 errors

---

### Step 2: Wire TenantMiddleware into src/main.py

Find the `app = FastAPI(...)` block in `src/main.py` and add `app.add_middleware(TenantMiddleware)` **after** the auth middleware registration line. The middleware must run after auth sets `auth_context` on `request.state`.

Locate the app construction block in `src/main.py` and insert:

```python
from src.internal.middleware.tenant_middleware import TenantMiddleware

app.add_middleware(TenantMiddleware)
```

**完成判定**：`ruff check src/main.py` → 0 errors

---

### Step 3: Create tests/unit/test_tenant_middleware.py

Create the test file with three test functions using `pytest` and the mock infrastructure from `tests/unit/conftest.py`. Each test uses `make_mock_session` with appropriate handlers. Use `MockState` for any stateful mocks.

```python
import pytest
from unittest.mock import MagicMock
from starlette.requests import Request

from src.internal.middleware.tenant_middleware import (
    TenantMiddleware, get_tenant_id, require_tenant, set_tenant_id
)
from pkg.errors.app_exceptions import UnauthorizedException


class TestRequiresTenant:
    def test_middleware_requires_tenant(self):
        mock_request = MagicMock(spec=Request)
        del mock_request.state.tenant_id
        with pytest.raises(UnauthorizedException) as exc_info:
            require_tenant(mock_request)
        assert "Tenant context required" in str(exc_info.value)


class TestAllowsValidTenant:
    def test_middleware_allows_valid_tenant(self, mock_db_session):
        mock_request = MagicMock(spec=Request)
        mock_request.state.tenant_id = 42
        tid = require_tenant(mock_request)
        assert tid == 42


class TestCrossTenantBlocked:
    def test_cross_tenant_blocked(self, mock_db_session):
        from src.services.activity_service import ActivityService
        svc = ActivityService(mock_db_session)
        mock_request = MagicMock(spec=Request)
        mock_request.state.tenant_id = 1
        with pytest.raises(ForbiddenException):
            svc.get_activity(activity_id=999, tenant_id=2)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tenant_middleware.py -v` → ≥ 5 passed

---

### Step 4: Verify all checks

Run the full lint + type check pipeline on the new file.

**完成判定**：`PYTHONPATH=src ruff check src/internal/middleware/tenant_middleware.py src/main.py && PYTHONPATH=src mypy src/internal/middleware/tenant_middleware.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/internal/middleware/tenant_middleware.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/internal/middleware/tenant_middleware.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_tenant_middleware.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src ruff check src/internal/middleware/tenant_middleware.py` → 0 errors
- [ ] Unit tests cover all three scenarios: no tenant → `UnauthorizedException`, valid tenant → passes, cross-tenant → `ForbiddenException` via mock service

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Auth middleware does not set `request.state.auth_context` before TenantMiddleware runs — tenant_id is always None | 中 | 高 | Reorder middleware: ensure `TenantMiddleware` is added **after** auth middleware in `main.py`; add a comment in the registration block |
| `Base.metadata.tables` lookup fails for complex queries with joins across multiple tables | 低 | 中 | `filter_by_tenant` raises `ValidationException` on ambiguity — callers can fall back to explicit `where(table.c.tenant_id == tenant_id)` for multi-table queries |
| `require_tenant` raises in non-HTTP contexts (background tasks, CLI scripts) where `request` is not a Starlette Request | 低 | 中 | Background tasks should receive `tenant_id` explicitly as a function argument; `require_tenant` is scoped to HTTP request handlers only |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/internal/middleware/tenant_middleware.py src/main.py tests/unit/test_tenant_middleware.py
git commit -m "feat(middleware): implement TenantMiddleware and require_tenant dependency"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#473): implement TenantMiddleware and require_tenant dependency" --body "Closes #473"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/internal/middleware/fastapi_auth.py`](../../src/internal/middleware/fastapi_auth.py) — existing ASGI middleware pattern (AuthContext + require_auth) to mirror
- 第三方文档：Starlette `BaseHTTPMiddleware` — https://www.starlette.io/middleware/#basehttpmiddleware
- 父 issue / 关联：#447, #472

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
