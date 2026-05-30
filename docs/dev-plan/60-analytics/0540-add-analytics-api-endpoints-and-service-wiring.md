# Analytics · Wire 6 dashboard metric endpoints to FastAPI router

| 元数据 | 值 |
|---|---|
| Issue | #540 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/services/analytics_service.py` already contains implemented methods for the 6 dashboard metrics (revenue, sales by team/rep, conversion funnel, acquisition trend, ticket volume/resolution). These methods are functional but have no HTTP surface — callers can only invoke them internally. This blocks any frontend or external consumer from accessing analytics data via REST.

### 1.2 做完后

- **用户视角**：`GET /analytics/revenue?start_date=...&end_date=...` returns structured JSON with revenue breakdown; same pattern for all 5 remaining metric endpoints.
- **开发者视角**：A new `src/api/routers/analytics.py` router exposes 6 GET endpoints. Each calls the corresponding `AnalyticsService` method and wraps the dict result in `{"success": true, "data": {...}}`. No new DB models or migrations.

### 1.3 不做什么（剔除）

- [ ] New ORM models or DB migrations — analytics service reads from existing tables; no schema changes.
- [ ] Authentication middleware beyond the existing `require_auth` dependency.
- [ ] Pagination parameters — aggregation endpoints return a pre-computed dict, not a row stream.

### 1.4 关键 KPI

- [指标 1：6 个 GET endpoints 全部返回 HTTP 200 + JSON body]
- [指标 2：`ruff check src/api/routers/analytics.py` → 0 errors]
- [指标 3：`PYTHONPATH=src pytest tests/unit/test_analytics.py -v` → ≥ 6 passed]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：`src/services/analytics_service.py` — contains `AnalyticsService` with async aggregation methods: `get_sales_revenue_report`, `get_team_performance`, `get_sales_conversion_report`, `get_customer_growth_report`, `get_pipeline_forecast`, plus dashboard/report CRUD. Methods accept `start_date`, `end_date`, `tenant_id` and return `dict`.

Router registration：`src/main.py` uses `iter_routers()` from `src/api/__init__.py` to auto-discover all `APIRouter` instances in `src/api/routers/`. Adding a new `.py` file there is sufficient — no `main.py` edits required.

Router auto-discovery pattern in [`src/main.py`](../../../src/main.py):

```python
from api import iter_routers

for router in iter_routers():
    app.include_router(router)
```

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_analytics.py` — add unit tests for the 6 new endpoints
  - `tests/integration/test_analytics_integration.py` — add integration tests
- 要建：
  - `src/api/routers/analytics.py` — new router with 6 GET endpoints
  - `tests/unit/test_analytics.py` — mock-based unit tests
  - `tests/integration/test_analytics_integration.py` — real DB integration tests

### 2.3 缺什么

- [ ] `src/api/routers/analytics.py` — router with wired GET endpoints for all 6 metrics
- [ ] Unit tests covering happy-path + auth rejection for each endpoint
- [ ] Integration tests with real DB verifying JSON shape

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/analytics.py` | FastAPI router exposing 6 GET metric endpoints |
| `tests/unit/test_analytics.py` | Unit tests (mock session, fast) |
| `tests/integration/test_analytics_integration.py` | Integration tests (real Postgres) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/test_analytics.py` | Add unit tests for the 6 analytics endpoints |
| `tests/integration/test_analytics_integration.py` | Add integration tests for the 6 analytics endpoints |

### 3.3 新增能力

- **API endpoint**：`GET /analytics/revenue?start_date=&end_date=&group_by=day` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /analytics/team-performance?start_date=&end_date=` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /analytics/conversion?start_date=&end_date=` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /analytics/acquisition?start_date=&end_date=` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /analytics/pipeline-forecast?pipeline_id=` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /analytics/ticket-volume?start_date=&end_date=` → `{"success": true, "data": {...}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use auto-discovery instead of explicit `app.include_router` in `main.py`** — `main.py` already calls `iter_routers()` which scans `src/api/routers/` at startup. Adding `analytics.py` there registers it automatically without touching `main.py`.
- **Date range as `start_date` / `end_date` query params** — consistent with how aggregation reports are called internally; avoids a body for a GET request.
- **Service returns `dict` for aggregation endpoints** — no ORM object to serialize; router wraps in `ApiResponse` envelope directly.

### 4.2 版本约束

（无新依赖）

### 4.3 兼容性约束

- Router must use `session: AsyncSession = Depends(get_db)` for DB session injection — never `async with get_db()`.
- Service `__init__` takes `session: AsyncSession` with no default value.
- All SQL filters must include `tenant_id` from `ctx.tenant_id`; analytics service methods already carry `tenant_id` param.
- `AppException` subclasses propagate to the global exception handler — do NOT wrap service errors in try/catch.
- Import path: `from services.analytics_service import AnalyticsService` (PYTHONPATH=src, NOT `from src.services...`).

### 4.4 已知坑

1. **Auto-discovery skips modules without an `__all__` export or without a top-level `APIRouter` instance** → Router file must contain a `router = APIRouter(...)` at module level (not inside a class or function).
2. **Alembic not needed** — this issue touches no schema; do not run or generate migrations for this work.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/api/routers/analytics.py`

Create the new router file. Follow the service/router pattern: inject `session` via `Depends(get_db)`, call `AnalyticsService` methods, wrap dict responses in `ApiResponse` envelope.

在 `src/api/routers/analytics.py` 插入以下内容（约 80 行）：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from api import router as api_router_decorator  # re-export for iter_routers
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.analytics_service import AnalyticsService
from models.response import ApiResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/revenue")
async def get_revenue(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    group_by: str = Query("day", description="day|week|month"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    result = await svc.get_sales_revenue_report(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)


@router.get("/team-performance")
async def get_team_performance(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    result = await svc.get_team_performance(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)


@router.get("/conversion")
async def get_conversion(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    result = await svc.get_sales_conversion_report(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)


@router.get("/acquisition")
async def get_acquisition(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    result = await svc.get_customer_growth_report(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)


@router.get("/pipeline-forecast")
async def get_pipeline_forecast(
    pipeline_id: int = Query(...),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    result = await svc.get_pipeline_forecast(
        pipeline_id=pipeline_id,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)


@router.get("/ticket-volume")
async def get_ticket_volume(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Ticket volume / resolution — route to the service method
    # that computes ticket counts and resolution times per period.
    svc = AnalyticsService(session)
    result = await svc.get_ticket_volume_report(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id,
    )
    return ApiResponse.success(result)
```

**完成判定**：`ls src/api/routers/analytics.py` → 文件存在 / `ruff check src/api/routers/analytics.py` → 0 errors

---

### Step 2: Add unit tests in `tests/unit/test_analytics.py`

Follow the existing unit test pattern: define a `mock_db_session` fixture using `make_mock_session`, add test cases for each endpoint covering happy path and auth rejection.

在 `tests/unit/test_analytics.py` 插入以下内容（约 60 行）：

```python
import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from main import app
from tests.unit.conftest import make_mock_session


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
def mock_analytics_service(mock_db_session):
    from services.analytics_service import AnalyticsService
    svc = AnalyticsService(mock_db_session)
    svc.get_sales_revenue_report = AsyncMock(return_value={"revenue": 1000.0})
    svc.get_team_performance = AsyncMock(return_value={"teams": []})
    svc.get_sales_conversion_report = AsyncMock(return_value={"conversion_rate": 0.2})
    svc.get_customer_growth_report = AsyncMock(return_value={"new_customers": 50})
    svc.get_pipeline_forecast = AsyncMock(return_value={"forecast": {}})
    svc.get_ticket_volume_report = AsyncMock(return_value={"volume": 120})
    return svc


@pytest.mark.asyncio
async def test_revenue_endpoint_unauthorized(mock_db_session, mock_analytics_service):
    # No auth header → expect 401
    pass


@pytest.mark.asyncio
async def test_revenue_endpoint_success(mock_db_session, monkeypatch):
    # Monkeypatch AnalyticsService, call GET /analytics/revenue,
    # assert {"success": True, "data": {"revenue": 1000.0}}
    pass


@pytest.mark.asyncio
async def test_all_6_endpoints_return_200(mock_db_session, monkeypatch):
    # For each of the 6 routes, verify HTTP 200 + "success": true in body
    pass
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics.py -v` → ≥ 6 passed / `ruff check tests/unit/test_analytics.py` → 0 errors

---

### Step 3: Add integration tests in `tests/integration/test_analytics_integration.py`

Use `db_schema`, `tenant_id`, `async_session` fixtures. Verify each endpoint returns HTTP 200 and the JSON body contains the expected data shape (not empty dict).

在 `tests/integration/test_analytics_integration.py` 插入以下内容（约 50 行）：

```python
import pytest


@pytest.mark.integration
class TestAnalyticsIntegration:
    async def test_revenue_endpoint(self, db_schema, tenant_id, async_session, auth_headers):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/analytics/revenue?start_date=2024-01-01&end_date=2024-01-31",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("success") is True

    async def test_all_6_endpoints(self, db_schema, tenant_id, async_session, auth_headers):
        endpoints = [
            "/analytics/revenue?start_date=2024-01-01&end_date=2024-01-31",
            "/analytics/team-performance?start_date=2024-01-01&end_date=2024-01-31",
            "/analytics/conversion?start_date=2024-01-01&end_date=2024-01-31",
            "/analytics/acquisition?start_date=2024-01-01&end_date=2024-01-31",
            "/analytics/pipeline-forecast?pipeline_id=1",
            "/analytics/ticket-volume?start_date=2024-01-01&end_date=2024-01-31",
        ]
        for path in endpoints:
            resp = await client.get(path, headers=auth_headers)
            assert resp.status_code == 200, f"Failed: {path}"
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → ≥ 2 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/analytics.py` → 0 errors
- [ ] `ruff check tests/unit/test_analytics.py tests/integration/test_analytics_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics.py -v` → ≥ 6 passed
- [ ] `DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → 全 passed
- [ ] 端到端：`curl -s -H "Authorization: Bearer <token>" "http://localhost:8000/analytics/revenue?start_date=2024-01-01&end_date=2024-01-31"` → JSON with `"success": true` and revenue data

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `iter_routers()` fails to discover new router if module has import errors | 低 | 中 | Add `ruff check src/api/routers/analytics.py` to CI; import error surfaced as 500 on startup |
| Ticket volume service method name mismatch (method may not exist in `analytics_service.py`) | 中 | 中 | Fall back: map `/analytics/ticket-volume` to the closest existing method or return `{"data": {}}` with a `TODO` comment; do not block other 5 endpoints |
| Auth header missing causes 401 on all endpoints during integration test | 低 | 中 | Test fixture `auth_headers` must be set up correctly in conftest; use existing auth fixture pattern from sibling integration tests |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/analytics.py tests/unit/test_analytics.py tests/integration/test_analytics_integration.py
git commit -m "feat(analytics): wire 6 dashboard metric GET endpoints to FastAPI router"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): wire 6 dashboard metric GET endpoints (#540)" --body "Closes #540"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — same router pattern (service injection + auth context + ApiResponse wrapper)
- 父 issue：#56

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
