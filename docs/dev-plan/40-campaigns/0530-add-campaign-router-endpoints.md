# Campaign CRUD · Add /marketing/campaigns router endpoints

| 元数据 | 值 |
|---|---|
| Issue | #530 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [Campaign ORM + Service](40-campaigns/0529-campaign-orm-service-model.md) |
| 启用后赋能 | N/A — 本身为叶子板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #529 establishes the `CampaignService` and ORM model for campaigns. The application exposes no FastAPI route for any campaign operation today, so all campaign functionality remains inaccessible via HTTP. Any downstream consumer (frontend, external integration) is blocked without a router layer.

### 1.2 做完后

- **用户视角**：无直接用户-visible change. The REST contract for campaign CRUD + filter/sort/pagination + stats summary is now live at `POST/GET/PUT /marketing/campaigns` and `GET /marketing/campaigns/{id}/stats`.
- **开发者视角**：`src/api/routers/marketing.py` exposes five endpoints backed by `CampaignService`. Router handlers use `Depends(get_db)` for session injection, call the service directly, and wrap results in `ApiResponse(success=True, data=...)`.

### 1.3 不做什么（剔除）

- [ ] Implementing `CampaignService` itself — covered by #529.
- [ ] Adding WebSocket or SSE endpoints for campaign notifications.
- [ ] Adding campaign analytics beyond the single stats-summary endpoint.
- [ ] Integration tests — #531 (or #688) owns that scope.
- [ ] Replacing the service with raw SQL in the router; all DB access goes through `CampaignService`.

### 1.4 关键 KPI

- [ ] `ruff check src/api/routers/marketing.py` → 0 errors (0 warnings)
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing_router.py -v` → all passed- [ ] `PYTHONPATH=src pytest tests/integration/test_marketing_router_integration.py -v` → all passed
- [ ] All five endpoints respond with `{"success": true, "data": {...}}` (or correct error shape) for their happy-path inputs---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/marketing.py` — issue #529 creates it alongside `CampaignService`, but neither exists in master yet. Confirm with `ls src/api/routers/marketing.py` or `grep -r "campaign" src/api/routers/` before authoring the step. Assume the file will be on `master` when this board launches.

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/marketing.py` — add all five CRUD + stats endpoints
- 要建：
  - `tests/unit/test_marketing_router.py` — unit-level router handler tests with mocked service
  - `tests/integration/test_marketing_router_integration.py` — real-DB integration tests (passed to #531 / #688)

### 2.3 缺什么

- [ ] No `GET /marketing/campaigns` list endpoint
- [ ] No `GET /marketing/campaigns/{id}` single-get endpoint
- [ ] No `POST /marketing/campaigns` create endpoint
- [ ] No `PUT /marketing/campaigns/{id}` update endpoint
- [ ] No `GET /marketing/campaigns/{id}/stats` endpoint
- [ ] No unit or integration tests for the router layer

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_marketing_router.py` | Unit tests for all five `marketing.py` endpoints with mocked `CampaignService` |
| `tests/integration/test_marketing_router_integration.py` | Integration tests exercising real DB + real service (deferred to #531 / #688) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/marketing.py`](../../src/api/routers/marketing.py) | Add five endpoints: list (filter/sort/pagination), get_one, create, update, stats |

### 3.3 新增能力

- **API endpoint**：`GET /marketing/campaigns` list with query params `filter`, `sort_by`, `page`, `page_size`
- **API endpoint**：`GET /marketing/campaigns/{campaign_id}` get one by ID
- **API endpoint**：`POST /marketing/campaigns` create from request body
- **API endpoint**：`PUT /marketing/campaigns/{campaign_id}` update from request body
- **API endpoint**：`GET /marketing/campaigns/{campaign_id}/stats` return summary statistics
- All endpoints: authenticated via `Depends(require_auth)`, session via `Depends(get_db)`, response wrapped in `ApiResponse(success=True, data=...)`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Always delegate to service, never to raw SQL in the router.** Keeps the router thin and enforces business logic in `CampaignService` (established by #529). If a new query shape is needed, add a service method rather than bypassing the service.
- **No try/catch in router handlers.** The global `AppException` handler in `main.py` converts raised exceptions to JSON responses; per-handler try/catch would shadow that mechanism.
- **`.to_dict()` called in router, not service.** Per CLAUDE.md convention, services return ORM objects; routers serialize.

### 4.2 版本约束

N/A — no new dependencies introduced by this board.

### 4.3 兼容性约束

- All SQL queries via `CampaignService` add `WHERE tenant_id = :tenant_id` (multi-tenancy enforced by the service layer; router passes `tenant_id` from `AuthContext`).
- Router injects session via `session: AsyncSession = Depends(get_db)` — never `async with get_db()`.
- Service errors propagate as `AppException` subclasses; router does not catch them.
- Response shape: `{"success": true, "data": <serialized-result>}` for2xx; error shape is handled by the global exception handler.

### 4.4 已知坑

1. **CampaignService may not accept a `tenant_id` kwarg on every method** → Symptom: `TypeError` at runtime. If #529's service methods omit `tenant_id`, they must be updated before this board's endpoints can call them safely. Mitigation: coordinate with #529 to ensure all methods accept `tenant_id`.
2. **Router list endpoint query params (`filter`, `sort_by`) may not map cleanly to service method params** → Symptom: type mismatch between string query param and service-expectable filter dict. Mitigation: parse query string in the router handler before passing a typed filter object to the service.
3. **`router.register_routes()` called in `main.py` not yet updated for the new prefix** → If `APIRouter(prefix="/marketing", router=[...])` is not included in `main.py`, all endpoints return 404. Verify `main.py` includes the marketing router.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify CampaignService shape and confirm marketing.py exists

Identify exactly what `CampaignService` exposes (methods + signatures) and whether `marketing.py` is already present from #529.

操作：
- a) Run `grep -n "class CampaignService" src/services/marketing_service.py` to find the service class.
- b) Run `grep -n "def " src/services/marketing_service.py` to list all public method names and signatures.
- c) Check that `src/api/routers/marketing.py` exists (may have been created by #529):
  ```bash
  ls src/api/routers/marketing.py
  ```
- d) If the file does not exist yet, create it as a stub router with no endpoints yet:
  ```python
  from fastapi import APIRouter

  router = APIRouter(prefix="/marketing/campaigns", tags=["Campaigns"])
  ```

**完成判定**：`ls src/api/routers/marketing.py` exits0 AND `grep "CampaignService" src/services/marketing_service.py` finds the class.

---

### Step 2: Add list, get-one, create, update, stats endpoints to marketing.py

Read the existing `marketing.py` stub (or confirm it does not exist) and add the five endpoints.

在 `src/api/routers/marketing.py` 中添加以下端点：

```python
# src/api/routers/marketing.py
from fastapi import APIRouter, Dependsfrom sqlalchemy.ext异步 import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.campaign_service import CampaignService
from api.deps import ApiResponse

router = APIRouter(prefix="/marketing/campaigns", tags=["Campaigns"])

@router.get("/")
async def list_campaigns(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    filter_status: str | None = None,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CampaignService(session)
    items, total = await svc.list_campaigns(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filter_status=filter_status,
    )
    return ApiResponse(success=True, data={
        "items": [c.to_dict() for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })

@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CampaignService(session)
    campaign = await svc.get_campaign(campaign_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=campaign.to_dict())

@router.post("/")
async def create_campaign(
    payload: CreateCampaignPayload,   # imported from src.models.campaign
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CampaignService(session)
    campaign = await svc.create_campaign(payload.model_dump(), tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=campaign.to_dict())

@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    payload: UpdateCampaignPayload,   # imported from src.models.campaign
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CampaignService(session)
    campaign = await svc.update_campaign(campaign_id, payload.model_dump(), tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=campaign.to_dict())

@router.get("/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CampaignService(session)
    stats = await svc.get_stats(campaign_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=stats)
```

**完成判定**：`ruff check src/api/routers/marketing.py` exits 0.

---

### Step 3: Wire router into main.py

Confirm that `src/main.py` includes the marketing router, or add it.

操作：
- a) In `src/main.py`, after the existing router registrations add:
  ```python
  from api.routers import marketing
  app.include_router(marketing.router)
  ```
- b) If the prefix is `router = APIRouter(prefix="/marketing/campaigns", ...)` inside `marketing.py`, the final path is `/marketing/campaigns`; no further prefix needed on `include_router`.

**完成判定**：`grep "marketing" src/main.py` finds the include_router call.

---

### Step 4: Write unit tests for all five endpoints

Create `tests/unit/test_marketing_router.py` following the existing unit test pattern — mocked service, `TestClient` over `app`.

```python
# tests/unit/test_marketing_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from api.routers.marketing import routerfrom internal.middleware.fastapi_auth import AuthContext

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def mock_auth():
    return AuthContext(tenant_id=1, user_id=1)

@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.list_campaigns = AsyncMock(return_value=([], 0))
    svc.get_campaign = AsyncMock(return_value=MagicMock(to_dict=lambda: {}))
    svc.create_campaign = AsyncMock(return_value=MagicMock(id=1, to_dict=lambda: {"id": 1}))
    svc.update_campaign = AsyncMock(return_value=MagicMock(id=1, to_dict=lambda: {"id": 1}))
    svc.get_stats = AsyncMock(return_value={"sent": 0, "opened": 0, "clicked": 0})
    return svc

def test_list_campaigns(app, mock_service, mock_auth, mocker):
    mocker.patch("services.campaign_service.CampaignService", return_value=mock_service)
    client = TestClient(app)
    # exercise patched auth + session mocker
    ...
```

**完成判定**：`PYTHONPATH=src pytest tests单元/test_marketing_router.py -v` → all passed.

---

### Step 5: Run the full verification suite

执行所有验收命令并确认输出符合预期。

操作：
- a) `ruff check src/api/routers/marketing.py tests/unit/test_marketing_router.py` →0 errors
- b) `PYTHONPATH=src pytest tests/unit/test_marketing_router.py -v` → all passed
- c) `PYTHONPATH=src pytest tests/integration/test_marketing_router_integration.py -v` → all passed (if integration tests exist; skip if they belong to #531)
- d) `curl -X GET http://localhost:8000/marketing/campaigns?page=1&page_size=20` returns `{"success": true, "data": {"items": [], "total": 0, ...}}` (requires the app to be running with a seeded DB)

**完成判定**：所有四条命令符合 §6 "验收" 中声明的预期输出。

---

## 6. 验收

- [ ] `ruff check src/api/routers/marketing.py tests/unit/test_marketing_router.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing_router.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_marketing_router_integration.py -v` → all passed (defer to #531 if not yet written)
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit-0 commands (run idempotently; required because list endpoint hits real DB in integration mode)
- [ ] End-to-end: `curl -s -X GET http://localhost:8000/marketing/campaigns?page=1` returns HTTP200 with body matching `{"success": true, "data": {"items": [], ...}}`
- [ ] End-to-end: `curl -s -X POST http://localhost:8000/marketing/campaigns -H "Content-Type: application/json" -d '{"name":"Q2 Launch","status":"draft"}'` returns HTTP 200 with `{"success": true, "data": {"id": ...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| CampaignService.list_campaigns signature does not match router's query param names (e.g., `sort_dir` vs `order`) | 中 | 中 | Sync param names before the step4 test run; update the router handler to match the service signature exactly |
| `src/main.py` router registration is missing and the `/marketing/campaigns` prefix 404s | 高 | 高 | Add `app.include_router(marketing.router)` to `src/main.py` in Step 3; treat missing registration as blocking |
| #529 service methods omit `tenant_id` on one or more methods | 中 | 高 | Coordinate with #529 before Step 2; all service methods must accept `tenant_id` — blocking, do not skip |
| Integration test DB seed does not include a campaign row | 低 | 中 | Add `_seed_campaign` helper in `tests/integration/conftest.py` before running integration tests |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/api/routers/marketing.py tests/unit/test_marketing_router.py
git commit -m "feat(campaigns): add /marketing/campaigns router endpoints #530"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add /marketing/campaigns CRUD and stats endpoints" --body "Closes #530"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../src/api/routers/customers.py) — serves as the canonical router-pattern reference in this repo
- 同类参考实现：[`src/api/routers/sales.py`](../../src/api/routers/sales.py) — list + get + create + update pattern with filter/sort/pagination
- 父 issue / 关联：#62- 依赖的前置板块：#529

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
