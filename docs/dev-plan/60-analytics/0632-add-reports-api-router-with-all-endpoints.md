# Reports · Add Reports API router with all endpoints

| 元数据 | 值 |
|---|---|
| Issue | #632 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0631-build-reporting-service-with-generate-download](../50-automation/0631-build-reporting-service-with-generate-download.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #632 requires exposing the Reports domain via a FastAPI router. The ReportsService built in issue #631 provides generate/download logic, but without a router layer it is inaccessible to API clients. Every feature workstream that needs reporting (dashboards, scheduled exports, analytics exports) is blocked until these endpoints exist.

### 1.2 做完后

- **用户视角**: API clients can list reports, create reports, retrieve a single report, trigger async generation, download report files, and manage scheduled report jobs via HTTP.
- **开发者视角**: Any service can call `ReportsService(session)` and use its methods; the router layer wraps those in `ApiResponse` envelopes. The new router is mounted at `/reports` in `src/main.py`.

### 1.3 不做什么（剔除）

- [ ] Implementing the Report SQL model itself — handled by issue #631.
- [ ] Implementing the ReportsService business logic — handled by issue #631.
- [ ] Any file storage / S3 integration for download — handled by issue #631.
- [ ] Implementing schedule persistence (DB table for scheduled jobs) beyond the service stub.

### 1.4 关键 KPI

- [ ] `ruff check src/api/routers/reports.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → all cases passed
- [ ] Router registered in `src/main.py` — `/reports` prefix reachable
- [ ] All 7 endpoints present in router: GET /, POST /, GET /{id}, POST /{id}/generate, GET /{id}/download, POST /schedule, DELETE /{id}

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：确认 `src/services/reports_service.py` exists from issue #631 before writing §2. If not yet merged, §2.1 references the pending service with the expectation that it will exist by implementation time.

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — register `reports` router
- 要建：
  - `src/api/routers/reports.py` — Reports CRUD + generate/download + schedule router
  - `tests/unit/test_reports_router.py` — unit tests for all 7 endpoints

### 2.3 缺什么

- [ ] `src/api/routers/reports.py` does not exist — no HTTP surface for reports domain
- [ ] `src/main.py` does not register any reports router
- [ ] No unit tests for the reports router

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/reports.py` | Reports API router with 7 endpoints |
| `tests/unit/test_reports_router.py` | Unit tests for all reports router endpoints |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | Import and mount `reports` router at `/reports` prefix |

### 3.3 新增能力

- **API endpoint**：`GET /reports` → list reports (paginated)
- **API endpoint**：`POST /reports` → create report
- **API endpoint**：`GET /reports/{id}` → get single report
- **API endpoint**：`POST /reports/{id}/generate` → trigger async generation
- **API endpoint**：`GET /reports/{id}/download` → download generated report file
- **API endpoint**：`POST /reports/schedule` → create scheduled report job
- **API endpoint**：`DELETE /reports/{id}` → delete report

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **ApiResponse envelope** vs raw dict: Chosen per project convention — all routers return `{"success": true, "data": ...}`. No `OrjsonResponse` or direct `Response` subclasses.
- **`AuthContext` via `Depends(require_auth)`** vs session-level auth: Consistent with all existing routers; auth context is injected per-request.
- **Router methods call service then serialize with `.to_dict()`** vs returning ORM directly: Per CLAUDE.md router rules — services return ORM objects, routers handle serialization.

### 4.2 版本约束

N/A — no new dependencies.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (enforced in service layer, not router).
- Service returns ORM/dataclass objects, **does not** call `.to_dict()`; serialization by router.
- Service errors raise `AppException` subclasses — router has no try/catch; global handler in `main.py` catches them.
- Router session: `session: AsyncSession = Depends(get_db)` — never `async with get_db()`.

### 4.4 已知坑

1. **Router file imported before service is defined** → if `src/services/reports_service.py` does not exist at import time, router will fail to load. → Mitigation: block on issue #631 being merged first; if not possible, add `if TYPE_CHECKING` import guard.
2. **ApiResponse envelope conflicts with OpenAPI schema** → returning `{"success": true, "data": ...}` everywhere means OpenAPI sees raw dicts. → Current project convention accepts this; not fixing in this issue.

---

## 5. 实现步骤（按顺序）

### Step 1: Create the ReportsService stub reference and confirm contract

Confirm that `src/services/reports_service.py` exposes the following interface (from issue #631):

```python
class ReportsService:
    def __init__(self, session: AsyncSession): ...
    async def list_reports(self, tenant_id: int, page: int, page_size: int) -> tuple[list[ReportModel], int]: ...
    async def get_report(self, report_id: int, tenant_id: int) -> ReportModel: ...
    async def create_report(self, data: CreateReportSchema, tenant_id: int) -> ReportModel: ...
    async def generate_report(self, report_id: int, tenant_id: int) -> ReportModel: ...
    async def get_download_url(self, report_id: int, tenant_id: int) -> str: ...
    async def delete_report(self, report_id: int, tenant_id: int) -> None: ...
    async def create_schedule(self, data: CreateScheduleSchema, tenant_id: int) -> ScheduleModel: ...
```

If the service file does not exist yet, write a minimal stub in `src/services/reports_service.py` so the router can import it. The stub will be replaced when issue #631 lands.

**完成判定**: `PYTHONPATH=src python -c "from services.reports_service import ReportsService; print('ok')"` → exit 0

### Step 2: Create src/api/routers/reports.py

Write the router with all 7 endpoints. Each endpoint pattern:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ApiResponse
from services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/")
async def list_reports(
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    items, total = await svc.list_reports(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return ApiResponse(success=True, data={"items": [r.to_dict() for r in items], "total": total, "page": page, "page_size": page_size})

@router.post("/")
async def create_report(
    body: CreateReportSchema,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    report = await svc.create_report(data=body, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=report.to_dict())

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    report = await svc.get_report(report_id=report_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=report.to_dict())

@router.post("/{report_id}/generate")
async def generate_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    report = await svc.generate_report(report_id=report_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=report.to_dict())

@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    url = await svc.get_download_url(report_id=report_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data={"url": url})

@router.post("/schedule")
async def create_schedule(
    body: CreateScheduleSchema,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    schedule = await svc.create_schedule(data=body, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=schedule.to_dict())

@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = ReportsService(session)
    await svc.delete_report(report_id=report_id, tenant_id=ctx.tenant_id)
    return ApiResponse(success=True, data=None)
```

Import `CreateReportSchema` and `CreateScheduleSchema` from `src/models/schemas/report.py` (created by issue #631).

**完成判定**: `ruff check src/api/routers/reports.py` → 0 errors

### Step 3: Register router in src/main.py

Locate the existing router imports and registration block in `src/main.py`. Add:

```python
from api.routers.reports import router as reports_router
```

Add to the app construction (typically `app.include_router(...)` section):

```python
app.include_router(reports_router)
```

**完成判定**: `ruff check src/main.py` → 0 errors

### Step 4: Write unit tests for reports router

Create `tests/unit/test_reports_router.py` with at least:
- Mock `ReportsService` returning expected ORM objects
- Mock `get_db` and `require_auth` dependencies
- Test each of the 7 endpoints

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from main import app
from internal.middleware.fastapi_auth import AuthContext

# fixtures: mock_session, mock_auth_ctx, mock_reports_service, async_client
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → all cases passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/reports.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → all passed
- [ ] All 7 endpoints defined in `src/api/routers/reports.py`: GET /, POST /, GET /{id}, POST /{id}/generate, GET /{id}/download, POST /schedule, DELETE /{id}
- [ ] Router registered in `src/main.py` with `/reports` prefix
- [ ] Each endpoint uses `AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ReportsService from issue #631 not merged before implementation | 中 | 中 | Write stub service methods in `src/services/reports_service.py` as placeholder; replace when issue #631 lands |
| Service schema classes (CreateReportSchema, CreateScheduleSchema) not available | 中 | 高 | Add minimal Pydantic schemas inline in router file; remove once issue #631 provides them |
| Router import fails due to service not existing at import time | 低 | 高 | Use `TYPE_CHECKING` guard for service imports; run behind feature flag |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/reports.py src/main.py tests/unit/test_reports_router.py
git commit -m "feat(reports): add API router with all 7 endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(reports): add API router with all 7 endpoints" --body "Closes #632"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py)
- 同类参考实现：[`src/api/routers/campaigns.py`](../../src/api/routers/campaigns.py)
- 父 issue / 关联：#40
- 前置依赖：#631

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
