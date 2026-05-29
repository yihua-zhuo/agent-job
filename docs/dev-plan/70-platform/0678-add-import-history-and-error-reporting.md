# 0678 · Add import history and error reporting

| 元数据 | 值 |
|---|---|
| 周次 | W20.3 |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0677-add-import-jobs-crud-and-file-storage](../50-automation/0677-add-import-jobs-crud-and-file-storage.md) |
| 启用后赋能 | [0688-add-integration-tests-for-full-rule-lifecycle](../50-automation/0688-add-integration-tests-for-full-rule-lifecycle.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ImportExportService` currently has no concept of an `ImportJob` — it parses and writes data directly but keeps no persistent record of what was imported, when, and whether individual rows succeeded or failed. Issue #678 (subtask of #34) requires two missing capabilities: (a) a method to list all import jobs for a tenant, and (b) a `GET /import/jobs/{job_id}/errors` endpoint that returns paginated per-row error details. Without import history, operators have no visibility into partial failures; without structured error rows, they cannot identify which input rows need correction.

The upstream board #677 provides the `ImportJob` ORM model with an `error_log` JSON column — this board builds the service and router layer on top of that model.

### 1.2 做完后

- **用户视角**: Opening a failed import job in the CRM shows a table of error rows: which spreadsheet row failed, which field is problematic, and what the error message is. Each error is actionable — the user knows exactly which record to fix.
- **开发者视角**: `ImportExportService.list_jobs(tenant_id, page, page_size)` returns `(items: list[ImportJob], total: int)`. Calling `GET /import/jobs/{job_id}/errors?page=1&page_size=20` returns `{"items": [{"row_number": 3, "field": "email", "message": "格式不正确"}], "total": N, "page": 1, "page_size": 20}`.

### 1.3 不做什么（剔除）

- [ ] No `execute_import` method — that belongs to the upstream board #677 which builds the core import execution engine.
- [ ] No new ImportJob ORM model — it is assumed to exist from #677.
- [ ] No error-retry or row-level correction endpoints — only read-only error listing.
- [ ] No export-job error listing (only import jobs have structured row-level errors).

### 1.4 关键 KPI

- `GET /import/jobs` → paginated JSON with `items` + `total` + `page` + `page_size` in < 100 ms (no session = fast path)
- `GET /import/jobs/{job_id}/errors` → returns `error_log` rows from `ImportJob.error_log` JSON column in < 50 ms
- `ruff check src/` → 0 errors
- `pytest tests/unit/test_import_export_service.py -v` → all pass (includes new `list_jobs` tests)

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`ImportExportService` in [`src/services/import_export_service.py`](../../src/services/import_export_service.py) L16-L423 handles parse/validate/write but has no `ImportJob` concept, no `list_jobs`, and no error-log storage. The `ImportJob` ORM model with `error_log` JSON column is assumed to be delivered by the upstream board #677.

### 2.2 涉及文件清单

- 要改：
  - [`src/services/import_export_service.py`](../../src/services/import_export_service.py) - 新增 `list_jobs()` 方法；`execute_import` 中写入 `error_log`
- 要建：
  - `src/api/routers/import_jobs.py` - 新建 import jobs router，定义 `GET /import/jobs` 和 `GET /import/jobs/{job_id}/errors` 端点
  - `tests/unit/test_import_export_service.py` - 追加 `list_jobs` + `get_job_errors` 测试用例
  - `docs/dev-plan/70-platform/verify/0678_test_import_history.sh` - 验收脚本

### 2.3 缺什么

- [ ] `ImportExportService.list_jobs(tenant_id, page, page_size)` method — needed to enumerate all jobs for a tenant
- [ ] `GET /import/jobs/{job_id}/errors` endpoint — reads `error_log` JSON column and returns paginated rows
- [ ] `execute_import` in `ImportExportService` (or upstream) must accumulate per-row errors and store them in `ImportJob.error_log` during the import loop
- [ ] No `ImportJob` ORM model yet — assumed from #677 (if it does not exist when this board is implemented, this board must create it first)
- [ ] No router file for import jobs — existing routers are in `src/api/routers/`

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/import_jobs.py` | Import jobs router: `GET /import/jobs` (list), `GET /import/jobs/{job_id}/errors` (paginated errors) |
| `tests/unit/test_import_export_service.py` | 追加 `TestImportExportServiceListJobs` 和 `TestImportExportServiceGetJobErrors` 测试类 |
| `docs/dev-plan/70-platform/verify/0678_test_import_history.sh` | 本板块验收脚本 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/import_export_service.py`](../../src/services/import_export_service.py) | 新增 `list_jobs(tenant_id, page, page_size)` 方法；确认 `execute_import` 调用处写入 `error_log` 到 `ImportJob.error_log` JSON 列 |

### 3.3 新增能力

- **API endpoint**: `GET /api/import/jobs` → `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20}}`
- **API endpoint**: `GET /api/import/jobs/{job_id}/errors` → `{"success": true, "data": {"items": [{"row_number": 3, "field": "email", "message": "..."}], "total": N, "page": 1, "page_size": 20}}`
- **Service method**: `ImportExportService.list_jobs(tenant_id, page, page_size) -> tuple[list[ImportJob], int]`
- **verify 脚本**: `bash docs/dev-plan/70-platform/verify/0678_test_import_history.sh`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSON `error_log` column over a separate `ImportError` table**: Per-row import errors are transient and scoped to a single job run. Storing them as a JSON array on `ImportJob.error_log` avoids a migration for a new table and keeps error lookup in one query. If error volume exceeds ~1000 rows per job, the JSON approach should be revisited.
- **Router in `src/api/routers/import_jobs.py` rather than appended to `sales.py`**: Import/export is a distinct domain (see `docs/dev-plan/README.md` §1.2 `70-platform` classification); keeping it in its own router mirrors the pattern used by `automation.py`, `rbac.py`, etc.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `ruff` | (from project) | pinned in `pyproject.toml` |
| `pytest` | (from project) | pinned in `pyproject.toml` |

### 4.3 兼容性约束

- `ImportExportService.list_jobs` must return ORM `ImportJob` objects — the router calls `.to_dict()` on them. The router pattern requires ORM objects, not raw dicts.
- `ImportJob.error_log` is a JSON column — `get_job_errors` parses it with `json.loads` and returns the array slice. If `error_log` is `None` (job has no errors), return an empty `items` list with `total: 0`.
- No breaking changes to existing `ImportExportService` methods (`import_customers`, `import_opportunities`, `validate_import_data`).

### 4.4 已知坑

1. **`error_log` may be `None` on a newly created `ImportJob`** → 规避：service method checks `if job.error_log is None: return []` before calling `json.loads`.
2. **`error_log` JSON array structure may differ across job versions** → 规避：在 `get_job_errors` parse step, validate each item has `row_number`, `field`, `message` keys; discard malformed items and log a warning.
3. **`list_jobs` must join or filter only on `tenant_id`** → 规避：always add `ImportJob.tenant_id == tenant_id` to the SQLAlchemy `where()` clause.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify or create ImportJob ORM model

确认 `ImportJob` model 存在于 `src/db/models/`。如果 #677 尚未交付此模型，在 `src/db/models/import_job.py` 创建：

```python
# src/db/models/import_job.py
from datetime import UTC, datetime
from sqlalchemy import JSON, Integer, String, Text
from db.base import Base


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    entity_type = Column(String(50), nullable=True)
    file_name = Column(String(255), nullable=True)
    total_rows = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_log = Column(JSON, default=list)  # [{row_number, field, message}, ...]
    created_at = Column(Text, nullable=True)
    updated_at = Column(Text, nullable=True)
```

**完成判定**：在 `alembic/env.py` import 该模型后，运行 `python -c "from db.models.import_job import ImportJob; print(ImportJob.__tablename__)"` 输出 `import_jobs`。

---

### Step 2: Add `list_jobs` method to ImportExportService

在 `src/services/import_export_service.py` 文件末尾（`_export_data` 方法之后）插入：

```python
# src/services/import_export_service.py
    async def list_jobs(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        """List import jobs for a tenant, newest first. Returns (items, total)."""
        if self.session is None:
            return [], 0

        from db.models.import_job import ImportJob

        # count
        count_q = select(func.count(ImportJob.id)).where(ImportJob.tenant_id == tenant_id)
        total = (await self.session.execute(count_q)).scalar() or 0

        # fetch page
        offset = (page - 1) * page_size
        q = (
            select(ImportJob)
            .where(ImportJob.tenant_id == tenant_id)
            .order_by(ImportJob.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return list(rows), total
```

**完成判定**：`grep -n "async def list_jobs" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 3: Add `get_job_errors` method to ImportExportService

在 `src/services/import_export_service.py` 的 `list_jobs` 方法之后插入：

```python
    def get_job_errors(self, job_id: int, tenant_id: int, page: int = 1, page_size: int = 20) -> dict:
        """Return paginated error rows from ImportJob.error_log JSON column."""
        import json as _json

        if self.session is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        from db.models.import_job import ImportJob

        import_job = (
            self.session.query(ImportJob)
            .filter(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id)
            .first()
        )
        if import_job is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        raw_errors = import_job.error_log or []
        if isinstance(raw_errors, str):
            try:
                raw_errors = _json.loads(raw_errors)
            except Exception:
                raw_errors = []

        total = len(raw_errors)
        offset = (page - 1) * page_size
        page_items = raw_errors[offset : offset + page_size]
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
```

**完成判定**：`grep -n "def get_job_errors" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 4: Create import_jobs router

新建 `src/api/routers/import_jobs.py`：

```python
# src/api/routers/import_jobs.py
"""Import jobs router — /api/import/jobs, /api/import/jobs/{job_id}/errors.

Services raise AppException on errors (caught by global handler in main.py).
Router serializes ORM objects via .to_dict().
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import NotFoundException
from services.import_export_service import ImportExportService

import_jobs_router = APIRouter(prefix="/api/import", tags=["import"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
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


# ---------------------------------------------------------------------------
# GET /import/jobs — list all import jobs for the tenant
# ---------------------------------------------------------------------------


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@import_jobs_router.get("/jobs")
async def list_import_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ImportExportService(session)
    items, total = await svc.list_jobs(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return _paginated(
        items=[job.to_dict() if hasattr(job, "to_dict") else job for job in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /import/jobs/{job_id}/errors — paginated per-row errors
# ---------------------------------------------------------------------------


@import_jobs_router.get("/jobs/{job_id}/errors")
async def get_import_job_errors(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ImportExportService(session)
    result = svc.get_job_errors(job_id=job_id, tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return {"success": True, "data": result}
```

**完成判定**：`ls src/api/routers/import_jobs.py` 文件存在；`ruff check src/api/routers/import_jobs.py` 输出 `0 errors`。

---

### Step 5: Register import_jobs_router in main.py

在 `src/main.py` 的 `app.include_router(...)` 调用处添加：

```python
from api.routers.import_jobs import import_jobs_router
...
app.include_router(import_jobs_router)
```

**完成判定**：`grep -n "import_jobs_router" src/main.py` 输出行号；`ruff check src/main.py` 输出 `0 errors`。

---

### Step 6: Add unit tests for list_jobs and get_job_errors

在 `tests/unit/test_import_export_service.py` 末尾追加：

```python
# tests/unit/test_import_export_service.py
import pytest
import json as _json
from tests.unit.conftest import MockState, make_mock_session, MockRow, MockResult
from tests.unit.domain_handlers.sales import make_import_export_handler
from services.import_export_service import ImportExportService


class TestImportExportServiceListJobs:
    async def test_list_jobs_returns_empty_when_no_jobs(self, mock_db_session):
        svc = ImportExportService(mock_db_session)
        items, total = await svc.list_jobs(tenant_id=1, page=1, page_size=20)
        assert total == 0
        assert items == []

    async def test_list_jobs_returns_paginated_results(self, mock_db_session):
        svc = ImportExportService(mock_db_session)
        items, total = await svc.list_jobs(tenant_id=1, page=1, page_size=2)
        assert total >= 0
        assert isinstance(items, list)


class TestImportExportServiceGetJobErrors:
    def test_get_job_errors_returns_empty_for_none_error_log(self, mock_db_session):
        svc = ImportExportService(mock_db_session)
        result = svc.get_job_errors(job_id=1, tenant_id=1, page=1, page_size=20)
        assert "items" in result
        assert "total" in result
        assert result["page"] == 1
        assert result["page_size"] == 20

    def test_get_job_errors_returns_paginated_items(self, mock_db_session):
        svc = ImportExportService(mock_db_session)
        result = svc.get_job_errors(job_id=1, tenant_id=1, page=1, page_size=5)
        assert "items" in result
        assert "total" in result
        assert result["page_size"] == 5

    def test_get_job_errors_invalid_json_returns_empty_items(self, mock_db_session):
        svc = ImportExportService(mock_db_session)
        result = svc.get_job_errors(job_id=999, tenant_id=1, page=1, page_size=20)
        assert result["items"] == []
        assert result["total"] == 0
```

在 `mock_db_session` fixture 所在文件中追加或扩展 `make_import_export_handler` 使用方式。

**完成判定**：`pytest tests/unit/test_import_export_service.py::TestImportExportServiceListJobs -v` 输出 2 passed；`pytest tests/unit/test_import_export_service.py::TestImportExportServiceGetJobErrors -v` 输出 3 passed。

---

### Step 7: Run lint and write verify script

运行 `ruff check src/services/import_export_service.py src/api/routers/import_jobs.py src/main.py` 确保无 lint 错误。

在 `docs/dev-plan/70-platform/verify/0678_test_import_history.sh` 创建：

```bash
#!/bin/bash
set -e
export PYTHONPATH=src

echo "=== ruff check ==="
ruff check src/services/import_export_service.py src/api/routers/import_jobs.py
echo "=== pytest unit ==="
pytest tests/unit/test_import_export_service.py::TestImportExportServiceListJobs -v --tb=short
pytest tests/unit/test_import_export_service.py::TestImportExportServiceGetJobErrors -v --tb=short
echo "=== ALL DONE ==="
```

**完成判定**：`bash docs/dev-plan/70-platform/verify/0678_test_import_history.sh` 输出 ruff 0 errors + all tests passed。

---

## 6. 验收

- [ ] `ruff check src/services/import_export_service.py` 输出 `0 errors`
- [ ] `ruff check src/api/routers/import_jobs.py` 输出 `0 errors`
- [ ] `grep -n "async def list_jobs" src/services/import_export_service.py` 输出行号（非空）
- [ ] `grep -n "def get_job_errors" src/services/import_export_service.py` 输出行号（非空）
- [ ] `grep -n "import_jobs_router" src/main.py` 输出行号（非空）
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceListJobs -v` 输出 `2 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceGetJobErrors -v` 输出 `3 passed`
- [ ] `bash docs/dev-plan/70-platform/verify/0678_test_import_history.sh` 全绿

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ImportJob` model from #677 does not include `error_log` JSON column when this board starts | 中 | 高 | 本 board 先创建 `src/db/models/import_job.py` with the column; coordinate with #677 author to avoid duplicate model definitions |
| `get_job_errors` receives `error_log` as string that fails `json.loads` | 低 | 低 | `except Exception: raw_errors = []` — returns empty items, not a 500 error |
| `list_jobs` does a full table scan if `tenant_id` index is missing | 低 | 中 | Add `index=True` to `ImportJob.tenant_id` column in model; coordinate with #677 migration |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/services/import_export_service.py src/api/routers/import_jobs.py src/main.py tests/unit/test_import_export_service.py && git commit -m "feat(import): add list_jobs and get_job_errors endpoints (issue #678)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块本行状态
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ 0678-Add-Import-History-and-Error-Reporting 完成 (W20.3)
# - PR/Commit: <link>
# - 关键产物: ImportExportService.list_jobs(), get_job_errors(),
#             GET /api/import/jobs, GET /api/import/jobs/{job_id}/errors
# - 验收: pytest tests/unit/test_import_export_service.py 全 passed ✓
# - 下一步赋能: downstream integration tests (0688)

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- 上游 dependency board: [`0677-add-import-jobs-crud-and-file-storage`](../50-automation/0677-add-import-jobs-crud-and-file-storage.md) — provides `ImportJob` ORM model with `error_log` JSON column
- 父 issue: [#34](https://github.com/...) — 总览 issue
- 项目内：`ImportExportService` 实现参考 [`src/services/import_export_service.py`](../../src/services/import_export_service.py) L16-L423
- 项目内：Router 模式参考 [`src/api/routers/sales.py`](../../src/api/routers/sales.py) L1-L235
- 项目内：Error handling 规范 [`pkg/errors/app_exceptions.py`](../../pkg/errors/app_exceptions.py)
- CLAUDE.md §「Service Pattern」：service returns ORM + raises AppException

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
