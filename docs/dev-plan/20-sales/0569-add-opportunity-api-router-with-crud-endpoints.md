# 商机 API 路由 · Add opportunity API router with CRUD endpoints

| 元数据 | 值 |
|---|---|
| Issue | #569 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#568](.//docs/dev-plan/20-sales/0568-build-opportunity-service-with-database-queries.md) |
| 启用后赋能 | TBD - 待补充：依赖 #568 的下游板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #569 is a direct subtask of #552 (the CRM Opportunity feature epic). Issue #568 builds the `OpportunityService` that exposes business-logic methods for list, create, update, and delete — but those methods are unusable without an API layer. Without this router, no HTTP client (frontend, mobile, or external integration) can interact with opportunity data.

### 1.2 做完后

- **用户视角**: No direct user-facing change — this is the API layer underpinning the opportunity feature. Once both #568 and #569 land, the frontend can wire CRUD UI to the endpoints.
- **开发者视角**: Any service or external client can call `GET /opportunities`, `POST /opportunities`, `PATCH /opportunities/{id}`, and `DELETE /opportunities/{id}` with proper tenant isolation. The `OpportunityService` from #568 is now reachable over HTTP.

### 1.3 不做什么（剔除）

- [ ] Business logic lives in `OpportunityService` (#568); this router only wires HTTP → service.
- [ ] No pagination beyond `page` + `page_size` query params (no cursor, no cursor-based); #568's service signature governs this.
- [ ] No authentication implementation — `require_auth` / `get_db` are consumed as provided dependencies.

### 1.4 关键 KPI

- `ruff check src/api/routers/opportunity.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_opportunity_router.py -v` → all pass (TBD count pending test authoring)
- `alembic upgrade head` → exit 0 (confirms migration from #568 applies cleanly)
- `PYTHONPATH=src pytest tests/integration/test_opportunity_integration.py -v` → all pass (after #568 integration tests land)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/` 目录下的现有路由文件（如 `customer.py` 或 `ticket.py`）作为同类实现参考，预期行 L?-L? 附近。

TBD - 待验证：`src/services/opportunity_service.py`（#568 产出物）是否存在，方法签名是否包含 `list_opportunities`, `create_opportunity`, `update_opportunity`, `delete_opportunity`。

TBD - 待验证：`src/api/routers/__init__.py` 是否已有 opportunity router 注册逻辑。

新建模块时，§2.1 直接写：N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/api/routers/__init__.py` — 注册 `opportunity` router 到 FastAPI app
  - TBD - 待验证：`src/main.py` — 确认 router 前缀注入点（如 `app.include_router(opportunity_router, prefix="/opportunities", tags=["Opportunities"])`）
- 要建：
  - `src/api/routers/opportunity.py` — CRUD 路由定义
  - `tests/unit/test_opportunity_router.py` — 单元测试（mock `OpportunityService`）
  - `tests/integration/test_opportunity_integration.py` — 集成测试（real DB, depends on #568）

### 2.3 缺什么

- [ ] `src/api/routers/opportunity.py` — the HTTP layer exposing `OpportunityService` (#568) over REST
- [ ] Router registration in `main.py` / `routers/__init__.py`
- [ ] Unit tests for all four endpoints with mocked service
- [ ] Integration tests exercising the full stack with real DB (deferred until #568 migration lands)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| [`src/api/routers/opportunity.py`](../../src/api/routers/opportunity.py) | CRUD router: GET /, POST /, PATCH /{id}, DELETE /{id} |
| [`tests/unit/test_opportunity_router.py`](../../tests/unit/test_opportunity_router.py) | Unit tests: mock `OpportunityService`, assert HTTP responses |
| [`tests/integration/test_opportunity_integration.py`](../../tests/integration/test_opportunity_integration.py) | Integration tests: real DB, full stack (depends on #568) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/__init__.py`](../../src/api/routers/__init__.py) | Import and re-export `opportunity_router` |
| [`src/main.py`](../../src/main.py) | `app.include_router(opportunity_router, prefix="/opportunities", tags=["Opportunities"])` |

### 3.3 新增能力

- **API endpoint**：`GET /opportunities` — list with optional `stage` filter + `page`/`page_size` pagination → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /opportunities` — create → `{"success": true, "data": {...}}`
- **API endpoint**：`PATCH /opportunities/{id}` — update → `{"success": true, "data": {...}}`
- **API endpoint**：`DELETE /opportunities/{id}` — delete → `{"success": true, "data": null}`
- **Router module**：`OpportunityRouter` using `Depends(require_auth)` and `Depends(get_db)`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Follow existing router pattern** (e.g., `customer.py`, `ticket.py`) rather than inventing a new one — consistency means less cognitive overhead for the team and easier onboarding.
- **No try/catch in router** — `AppException` subclasses raised by `OpportunityService` are caught by the global exception handler in `main.py`. This is enforced in CLAUDE.md and the template; violating it would duplicate error-handling logic.
- **`.to_dict()` only in router** — `OpportunityService` returns ORM/model objects; serialization is the router's responsibility per CLAUDE.md conventions.

### 4.2 版本约束

<!-- 无新依赖引入，整段保留为空 -->

### 4.3 兼容性约束

- Multi-tenant: every SQL query in `OpportunityService` (from #568) must filter by `tenant_id`; the router passes `tenant_id=ctx.tenant_id` on every call.
- Session injection: always `session: AsyncSession = Depends(get_db)` — never `async with get_db() as session:`.
- Service constructor: `OpportunityService(session)` with `session: AsyncSession` and no default value.
- Response envelope: always `{"success": true, "data": ...}` — even on DELETE where `data` is `null`.
- Error raising: service raises `AppException` subclasses only; router never returns `ApiResponse.error()`.

### 4.4 已知坑

1. **Router file registered twice** → 规避：确认 `opportunity_router` is included exactly once in `main.py` or `routers/__init__.py`, not both.
2. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()`** → 规避（如 #568 migration touches JSON columns）：检查 migration file，手动替换 `JSON()` → `JSONB()`；参考 CLAUDE.md §Alembic Migrations.
3. **Missing `tenant_id` index on new opportunity table** → 规避：在 #568 migration 中确认 `tenant_id` 列带有 `index=True`；Alembic autogen may omit it.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/api/routers/opportunity.py` skeleton

Create the router file with all four endpoint stubs, import `OpportunityService` from `#568` (placeholder import — confirm module path once #568 lands), and wire `AuthContext` + `AsyncSession` dependencies.

操作：
- a) Create `src/api/routers/opportunity.py`
- b) Import `OpportunityService` (path TBD — verify from #568 output; likely `from services.opportunity_service import OpportunityService`)
- c) Import dependency injectors: `from internal.middleware.fastapi_auth import AuthContext, require_auth` and `from db.connection import get_db`
- d) Define router: `router = APIRouter(prefix="/opportunities", tags=["Opportunities"])`

示例代码：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
# from services.opportunity_service import OpportunityService  # confirm path after #568 lands

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("/")
async def list_opportunities(
    stage: str | None = None,
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    items, total = await svc.list_opportunities(
        tenant_id=ctx.tenant_id,
        stage=stage,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post("/")
async def create_opportunity(
    data: OpportunityCreate,  # confirmed from #568
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    entity = await svc.create_opportunity(data, tenant_id=ctx.tenant_id)
    return {"success": True, "data": entity.to_dict()}


@router.patch("/{opportunity_id}")
async def update_opportunity(
    opportunity_id: int,
    data: OpportunityUpdate,  # confirmed from #568
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    entity = await svc.update_opportunity(opportunity_id, data, tenant_id=ctx.tenant_id)
    return {"success": True, "data": entity.to_dict()}


@router.delete("/{opportunity_id}")
async def delete_opportunity(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    await svc.delete_opportunity(opportunity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": None}
```

**完成判定**: `src/api/routers/opportunity.py` 存在，4 个 endpoint 函数签名正确，`ruff check src/api/routers/opportunity.py` exit 0

### Step 2: Register router in `src/api/routers/__init__.py`

操作：
- a) Open `src/api/routers/__init__.py`
- b) Add `from api.routers.opportunity import router as opportunity_router`
- c) Add `opportunity_router` to `__all__`

**完成判定**: `ruff check src/api/routers/__init__.py` exit 0

### Step 3: Include router in `src/main.py`

操作：
- a) Open `src/main.py`
- b) Import `opportunity_router` from `api.routers`
- c) Add `app.include_router(opportunity_router, prefix="/opportunities", tags=["Opportunities"])` inside the app construction block (before any other routes that might shadow `/opportunities`)

**完成判定**: `ruff check src/main.py` exit 0；grep `opportunity_router` in `src/main.py` returns ≥ 1 match

### Step 4: Write unit tests in `tests/unit/test_opportunity_router.py`

Use `tests/unit/conftest.py` pattern: define a local `mock_db_session` fixture (can be minimal since the router calls service methods directly, not raw SQL), and patch `OpportunityService` methods using `unittest.mock.AsyncMock`.

操作：
- a) Create `tests/unit/test_opportunity_router.py`
- b) `from unittest.mock import AsyncMock, patch`
- c) Test `GET /opportunities` → returns `{"success": True, "data": {"items": [...], "total": N}}`
- d) Test `POST /opportunities` → returns `{"success": True, "data": {...}}`
- e) Test `PATCH /opportunities/{id}` → returns `{"success": True, "data": {...}}`
- f) Test `DELETE /opportunities/{id}` → returns `{"success": True, "data": None}`
- g) Test `NotFoundException` from service → HTTP 404 response
- h) Test `ValidationException` from service → HTTP 422 response

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_opportunity_router.py -v` → all pass

### Step 5: Write integration test in `tests/integration/test_opportunity_integration.py`

After #568 migration lands (`alembic upgrade head` succeeds), write a test that uses `db_schema`, `tenant_id`, and `async_session` fixtures. Seed a customer first (cross-service dependency), then exercise all four endpoints against the real DB.

操作：
- a) Create `tests/integration/test_opportunity_integration.py`
- b) `@pytest.mark.integration`
- c) Test `POST /opportunities` → 201 or 200
- d) Test `GET /opportunities` → list includes created record
- e) Test `PATCH /opportunities/{id}` → updated fields reflected
- f) Test `DELETE /opportunities/{id}` → 404 on subsequent GET

**完成判定**: `PYTHONPATH=src pytest tests/integration/test_opportunity_integration.py -v` → all pass

---

## 6. 验收

- [ ] `ruff check src/api/routers/opportunity.py` → 0 errors
- [ ] `ruff check src/api/routers/__init__.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_router.py -v` → all pass
- [ ] `PYTHONPATH=src pytest tests/integration/test_opportunity_integration.py -v` → all pass (after #568 lands)
- [ ] `alembic upgrade head` → exit 0 (verifies #568 migration is applied; `opportunity` table present)
- [ ] `curl -s http://localhost:8000/opportunities -H "Authorization: Bearer <token>" | python -m json.tool` → `{"success": true, "data": ...}` (manual smoke test)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `OpportunityService` method signatures in #568 differ from router assumptions (e.g., extra params, renamed fields) | 低 | 高 — router calls break at runtime | Pin #569 review to after #568 is merged; update router parameter binding before merging #569 |
| Router registered twice (in both `__init__.py` and `main.py`) → FastAPI route conflict | 低 | 中 — duplicate route warning, one shadowed | Review `include_router` call count = 1 in final diff |
| Integration tests blocked because #568 migration not landed | 中 | 中 — #569 unit tests pass but integration coverage gaps | Land #568 first; #569 blocked on `alembic upgrade head` clean exit |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/opportunity.py src/api/routers/__init__.py src/main.py
git add tests/unit/test_opportunity_router.py tests/integration/test_opportunity_integration.py
git commit -m "feat(opportunity): add CRUD router with list/create/update/delete endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(opportunity): add API router with CRUD endpoints (#569)" --body "Closes #569"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：现有路由实现参考 `src/api/routers/customer.py` 或 `src/api/routers/ticket.py` 的 CRUD 模式
- 父 issue / 关联：#552（商机功能总览），#568（OpportunityService 构建），#569（本板块）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
