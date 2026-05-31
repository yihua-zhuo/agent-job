# Add missing endpoints to existing reports router

| 元数据 | 值 |
|---|---|
| Issue | #750 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |

---

## 1. 目标与背景

### 1.1 为什么做

The existing [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) already has CRUD + PDF/Excel/CSV export endpoints but is missing 3 endpoints defined in the parent issue #632: `POST /{id}/generate`, `GET /{id}/download`, and `POST /schedule`. Without these endpoints the analytics feature is incomplete and downstream consumers cannot trigger report generation or scheduling via the API.

### 1.2 做完后

- **用户视角**: API consumers can now call `POST /reports/{id}/generate` to trigger PDF generation, `GET /reports/{id}/download` to retrieve a download URL, and `POST /reports/schedule` to schedule a report.
- **开发者视角**: All 10 endpoints defined in #632 are present and registered. The router is auto-discovered via `iter_routers()` in [`src/api/__init__.py`](../../../src/api/__init__.py) — no `main.py` change required. `ruff check src/api/routers/reports.py` passes cleanly.

### 1.3 不做什么（剔除）

- [ ] Writing the underlying `ReportService` methods (`generate_pdf_report`, `get_download_url`, `schedule_report`) — those belong in the service layer; this board only adds the router endpoints.
- [ ] Adding new ORM models or migrations — no schema changes are required for this router work.
- [ ] Modifying `main.py` — the router is auto-discovered.

### 1.4 关键 KPI

- `ruff check src/api/routers/reports.py` → 0 errors
- Reading [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) confirms exactly 10 endpoint handlers are registered (3 existing + 3 new = 6 base + PDF/Excel/CSV + generate + download + schedule = 10)
- `PYTHONPATH=src pytest tests/unit/test_reports.py -v` → all passed (or test file created if none exists)

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/api/routers/reports.py`](../../../src/api/routers/reports.py) L{1}-L{?}

TBD - 待验证：`src/api/routers/reports.py` — 现有 reports router 完整内容（确认当前有多少个 endpoint，是否已有 generate/download/schedule）

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — 添加 3 个缺失 endpoint handler
  - [`src/services/report_service.py`](../../../src/services/report_service.py) — TBD — 确认 `generate_pdf_report`, `get_download_url`, `schedule_report` 方法签名（如果本 issue 只做 router 层，这些方法应已存在）
  - TBD - 待验证：`tests/unit/test_reports.py` — 文件是否存在，如存在则添加新 endpoint 的单元测试覆盖
- 要建：
  - TBD - 待验证：`tests/unit/test_reports.py` — 如文件不存在则新建

### 2.3 缺什么

- [ ] Missing endpoint: `POST /reports/{id}/generate` → calls `svc.generate_pdf_report`
- [ ] Missing endpoint: `GET /reports/{id}/download` → calls `svc.get_download_url` (or triggers generation then returns URL)
- [ ] Missing endpoint: `POST /reports/schedule` → calls `svc.schedule_report`
- [ ] No unit test coverage for the 3 new endpoints

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `tests/unit/test_reports.py` | 覆盖所有 10 endpoint handlers 的单元测试（如文件不存在则新建） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) | 添加 `POST /{id}/generate`、`GET /{id}/download`、`POST /schedule` 3 个 endpoint handlers |

### 3.3 新增能力

- **API endpoint**: `POST /reports/{id}/generate` — calls `ReportService.generate_pdf_report`, returns `{"success": true, "data": {...}}`
- **API endpoint**: `GET /reports/{id}/download` — calls `ReportService.get_download_url`, returns download URL or generation status
- **API endpoint**: `POST /reports/schedule` — calls `ReportService.schedule_report`, returns schedule confirmation

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Follow existing endpoint pattern** rather than inventing new patterns — all existing endpoints use `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`; the 3 new endpoints will use the same pattern.
- **Service-layer delegation**: endpoints call service methods; no business logic lives in the router. This keeps the router thin and testable.

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- Router must follow `require_auth` / `get_db` dependency injection pattern already used in the file.
- Service calls must pass `tenant_id=ctx.tenant_id` from `AuthContext`.
- Response envelope: `{"success": true, "data": ...}` — no direct `return` of raw objects.
- `AppException` subclasses raised by service are caught globally; no try/catch in router.

### 4.4 已知坑

1. **Auto-discovery via `iter_routers()`**: The router is auto-loaded from [`src/api/__init__.py`](../../../src/api/__init__.py) — do NOT manually register it in `main.py`, as that would cause double-registration.

---

## 5. 实现步骤（按顺序）

### Step 1: Read existing reports router

Read the full content of [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) to identify:
- Current endpoint count and their paths
- Import style and dependency injection pattern used
- Whether `generate_pdf_report`, `get_download_url`, and `schedule_report` service methods already exist in [`src/services/report_service.py`](../../../src/services/report_service.py)

操作：
- a) Read `src/api/routers/reports.py`
- b) Read `src/services/report_service.py` (确认 service 方法签名)

**完成判定**: 文件内容已知，下一步可精确编写 diff

---

### Step 2: Add 3 missing endpoint handlers to reports.py

在 `reports.py` 末尾或适当位置插入 3 个新 handler，遵循现有文件的 decorator / 依赖注入模式：

```python
@router.post("/{report_id}/generate")
async def generate_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ReportService(session)
    result = await svc.generate_pdf_report(report_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict()}

@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ReportService(session)
    result = await svc.get_download_url(report_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict()}

@router.post("/schedule")
async def schedule_report(
    schedule_data: ScheduleReportRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ReportService(session)
    result = await svc.schedule_report(schedule_data, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict()}
```

（如 `ScheduleReportRequest` Pydantic model 不存在，需在 [`src/models/`](../../../src/models/) 中创建或在 `reports.py` 顶部使用 `BaseModel` 内联定义）

操作：
- a) 在 `src/api/routers/reports.py` 中添加上述 3 个 handler
- b) 如需 `ScheduleReportRequest` schema，在 `src/models/` 创建或内联

**完成判定**: `ruff check src/api/routers/reports.py` → 0 errors

---

### Step 3: Run ruff check

操作：
- a) `ruff check src/api/routers/reports.py`

**完成判定**: exit 0，no lint errors

---

### Step 4: Verify endpoint count

重新读取修改后的 `reports.py`，人工或脚本统计 `@router.*` decorator 数量，确认共 10 个 endpoint。

操作：
- a) 读取 `src/api/routers/reports.py`
- b) 统计 `@router.get`、`@router.post`、`@router.put`、`@router.delete` 行数

**完成判定**: 10 个 endpoint decorators present

---

### Step 5: Add or update unit tests

如 `tests/unit/test_reports.py` 不存在，创建文件并添加 3 个新 endpoint 的测试：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])

@pytest.mark.asyncio
async def test_generate_report_endpoint(mock_db_session, monkeypatch):
    # mock ReportService.generate_pdf_report
    ...
```

如文件存在，在其末尾添加 3 个测试函数覆盖新 endpoint。

操作：
- a) 如 `tests/unit/test_reports.py` 不存在，创建文件
- b) 如文件存在，在文件中添加 3 个测试函数

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_reports.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/reports.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_reports.py -v` → all passed（若测试文件新建，执行 `touch tests/unit/test_reports.py` 后跳过此条直至 Step 5 完成）
- [ ] 读取 `src/api/routers/reports.py` 确认 10 个 `@router.*` decorator 存在
- [ ] `ruff format --check src/api/routers/reports.py` → 无需格式化变更（文件已通过 ruff check）
- [ ] `PYTHONPATH=src mypy src/api/routers/reports.py --no-error-summary` → 无新增 type errors（如 mypy 已配置）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Service methods `generate_pdf_report` / `get_download_url` / `schedule_report` don't exist yet | 低 | 中 | Router endpoints call non-existent service methods → 500 at runtime. 降级：先实现 service 方法再合并 router 变更。 |
| Duplicate route registration if manually added to `main.py` | 低 | 高 | Router is auto-discovered via `iter_routers()` — never call `app.include_router(reports.router)` manually. |
| `ScheduleReportRequest` schema needs new file in `src/models/` | 低 | 低 | 内联 `class ScheduleReportRequest(BaseModel)` 于 `reports.py` 顶部或创建 `src/models/reports.py` — minimal change. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/reports.py tests/unit/test_reports.py
git commit -m "feat(reports): add generate, download, schedule endpoints (#750)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(reports): add missing endpoints (#750)" --body "Closes #750"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/opportunities.py` — 现有 router 参考，endpoint + service 调用模式相同
- 父 issue / 关联：#632

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |

---

**Changes made:**
- **Line 52** (`tests/unit/test_reports.py`): Dropped the broken link; replaced with `TBD - 待验证：`text in both the file list (Section 2.2) and Section 2.3 prose, matching the board's own note that the file may need to be created.
- **Line 265** (`src/api/routers/opportunities.py`): Dropped the broken link in Section 9 (reference) and replaced with `TBD - 待验证：<short hint>` — this file is only a reference example and is non-essential to the board's execution.
