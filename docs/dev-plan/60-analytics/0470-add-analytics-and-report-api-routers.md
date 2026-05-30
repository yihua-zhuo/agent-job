# Analytics & Report API Routers · Add analytics and report API routers wired into main

| 元数据 | 值 |
|---|---|
| Issue | #470 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |

---

## 1. 目标与背景

### 1.1 为什么做

The platform currently lacks dedicated analytics and reporting API endpoints. Backend service capabilities exist (or are being added in sister issues) but are not exposed via HTTP routes. Without these routers, frontend dashboards and admin tools cannot query analytics data, and external integrations cannot programmatically fetch reports.

### 1.2 做完后

- **用户视角**：`POST /analytics/*` and `POST /reports/*` endpoints are available. Administrators can fetch analytics summaries and report data via the REST API. No manual UI steps required for API access.
- **开发者视角**：`src/api/routers/analytics.py` and `reports.py` are importable and registered in `src/main.py`. Each router follows the standard pattern: `session: AsyncSession = Depends(get_db)`, `ctx: AuthContext = Depends(require_auth)`, returns `{"success": true, "data": ...}` envelope. Service-layer code can be called directly without going through the HTTP layer.

### 1.3 不做什么（剔除）

- [ ] Implementing analytics or reporting business logic — this issue is about wiring routers, not implementing services
- [ ] Adding frontend dashboard components
- [ ] Adding push notification / Slack integration for reports
- [ ] Writing unit tests for the routers (integration tests are in scope per the issue)

### 1.4 关键 KPI

- [`ruff check src/api/routers/analytics.py src/api/routers/reports.py` → 0 errors]
- [Integration tests in `tests/integration/test_analytics_integration.py` all pass — `pytest tests/integration/test_analytics_integration.py -v` → `N passed`]
- [Both routers registered in `src/main.py` and accessible at `/analytics` and `/reports` prefixes]
- [Alembic migration (if schema changes are needed) upgrades and downgrades cleanly — `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../src/main.py) — register `analytics_router` and `reports_router` under `/analytics` and `/reports` prefixes
- 要建：
  - `src/api/routers/analytics.py` — analytics router with standard session/auth injection pattern
  - `src/api/routers/reports.py` — reports router with standard session/auth injection pattern
  - `tests/integration/test_analytics_integration.py` — integration tests for analytics router using `db_schema` and `async_session` fixtures

### 2.3 缺什么

- [ ] `src/api/routers/analytics.py` does not exist — analytics endpoints cannot be reached via HTTP]
- [ ] `src/api/routers/reports.py` does not exist — report endpoints cannot be reached via HTTP]
- [ ] `src/main.py` does not include analytics or reports routers — no route registration]
- [ ] No integration test coverage for analytics router behavior]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/analytics.py` | Analytics API router — exposes analytics endpoints under `/analytics` prefix |
| `src/api/routers/reports.py` | Reports API router — exposes reporting endpoints under `/reports` prefix |
| `tests/integration/test_analytics_integration.py` | Integration tests for analytics router using real Postgres fixtures |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | Import and register `analytics_router` and `reports_router` with `app.include_router()` under `/analytics` and `/reports` prefixes |

### 3.3 新增能力

- **Router module**：`src/api/routers/analytics.py` with standard `APIRouter(prefix="/analytics", tags=["Analytics"])`
- **Router module**：`src/api/routers/reports.py` with standard `APIRouter(prefix="/reports", tags=["Reports"])`
- **Route registration**：Both routers wired into `FastAPI` app instance in `src/main.py`
- **Integration test suite**：`tests/integration/test_analytics_integration.py` covering happy path and error cases

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Follow existing router pattern** — adopt the exact structure used by `TBD - 待验证：src/api/routers/ 目录下现有 router 文件（如 customers.py 或 activities.py）L? — 现有 router 注册方式**， rather than inventing a custom structure. This ensures consistency across the codebase and makes the new routers immediately recognizable to existing engineers.

### 4.2 版本约束

（无新增外部依赖）

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` — applied by services called from routers, not by routers themselves
- Router session injection: always `session: AsyncSession = Depends(get_db)` — never `async with get_db()`
- Router auth injection: always `ctx: AuthContext = Depends(require_auth)`
- Serialization: call `.to_dict()` on ORM objects in the router after receiving them from the service — services never call `.to_dict()`
- Error handling: routers do not wrap in try/except — `AppException` subclasses raised by services are caught by the global handler registered in `main.py`
- Response envelope: `{"success": true, "data": <serialized-result>}` returned from every endpoint

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()`** → If any analytics/reports schema uses JSON columns, manually change `JSON()` to `JSONB()` in the migration and add `server_default=text("'{}'")` for non-nullable columns
2. **`metadata` column name collision** → If any new ORM model uses a column named `metadata`, it will conflict with `Base.metadata` (the `MetaData` object) and raise an `ArgumentError` at class definition time — use `event_metadata`, `payload`, `attrs`, or `meta` instead
3. **Router import order in `main.py`** → If `analytics_router` or `reports_router` are imported before `get_db` is registered, FastAPI's dependency injection can fail silently in tests — ensure `get_db` dependency is available before the routers are included

---

## 5. 实现步骤（按顺序）

### Step 1: Create the analytics router skeleton

Create `src/api/routers/analytics.py`. Define an `APIRouter` with `prefix="/analytics"` and `tags=["Analytics"]`. Import `Depends` from `fastapi`, `AsyncSession` from `sqlalchemy.ext.asyncio`, `get_db` from `db.connection`, `AuthContext` and `require_auth` from `internal.middleware.fastapi_auth`, and `ApiResponse` from `models.response`. Define one placeholder endpoint (e.g., `GET /analytics/summary`) that calls a placeholder service method and returns the standard envelope. Do not use try/except — let `AppException` propagate.

```python
# src/api/routers/analytics.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ApiResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_analytics_summary(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # TODO: call AnalyticsService once implemented
    return ApiResponse.success(data={})
```

**完成判定**：`ruff check src/api/routers/analytics.py` → 0 errors / 文件存在

---

### Step 2: Create the reports router skeleton

Create `src/api/routers/reports.py`. Mirror the structure from Step 1 with `prefix="/reports"` and `tags=["Reports"]`. Define one placeholder endpoint (e.g., `GET /reports/list`) that returns the standard envelope with empty data.

```python
# src/api/routers/reports.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ApiResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/list")
async def list_reports(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # TODO: call ReportService once implemented
    return ApiResponse.success(data=[])
```

**完成判定**：`ruff check src/api/routers/reports.py` → 0 errors / 文件存在

---

### Step 3: Register both routers in `src/main.py`

Open `src/main.py` and add two import lines for `analytics_router` and `reports_router`. Then add two `app.include_router()` calls after the existing router registrations:

```python
from api.routers.analytics import router as analytics_router
from api.routers.reports import router as reports_router

app.include_router(analytics_router)
app.include_router(reports_router)
```

Place the new includes after the existing `app.include_router()` block, preserving alphabetical or thematic order as appropriate.

**完成判定**：`ruff check src/main.py` → 0 errors / `grep -n "analytics_router\|reports_router" src/main.py` returns 4 lines (2 imports + 2 include_router)

---

### Step 4: Write integration tests for the analytics router

Create `tests/integration/test_analytics_integration.py`. Use `db_schema` and `async_session` fixtures. Test the `/analytics/summary` endpoint: send a request with valid auth context and verify the response status is 200 and the envelope shape matches `{"success": true, "data": {...}}`. Use `pytest.mark.integration` decorator. Use `_seed_customer` / `_seed_user` helpers to set up tenant data if the analytics service requires it.

```python
# tests/integration/test_analytics_integration.py
import pytest
from httpx import AsyncClient
from app import app  # TBD - verify: FastAPI app import path in src/main.py

@pytest.mark.integration
class TestAnalyticsRouter:
    async def test_get_summary_returns_envelope(self, db_schema, tenant_id, async_session):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # seed tenant data
            # make authenticated request to /analytics/summary
            # assert response status == 200
            # assert "success" in response.json() and response.json()["success"] is True
            pass
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → `N passed` (exact count TBD based on test count)

---

## 6. 验收

- [ ] `ruff check src/api/routers/analytics.py src/api/routers/reports.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration；先 skip 如果当前无 migration）
- [ ] `ruff format --check src/api/routers/analytics.py src/api/routers/reports.py` → 0 non-compliant lines
- [ ] 端到端测试：`curl -s http://localhost:8000/analytics/summary -H "Authorization: Bearer <token>"` returns `{"success": true, ...}`（前提：API server 已启动，token 有效）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Router placeholder endpoints return empty data, delaying downstream integration | 中 | 中 | Mark endpoints as `TODO` with tracked issue; downstream板块 can implement service layer without router changes |
| Integration test fixture setup fails due to app import path mismatch in `src/main.py` | 低 | 中 | Verify `from app import app` import path or use `TestClient` from `fastapi.test_client`; adjust fixture setup in `conftest.py` |
| Alembic migration is needed for analytics schema but not captured in this issue | 低 | 高 | Issue #469 (dependency) should handle schema; if migration is missed, run `alembic revision --autogenerate -m "add analytics tables"` and review before merging |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/analytics.py src/api/routers/reports.py src/main.py tests/integration/test_analytics_integration.py
git commit -m "feat(analytics): add analytics and reports API routers"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add #470 analytics and reports API routers" --body "Closes #470"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：src/api/routers/ 目录下现有 router 文件（如 customers.py）L? — 现有 router 注册方式和标准 envelope 格式
- 父 issue / 关联：#448 (parent), #469 (dependency)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
