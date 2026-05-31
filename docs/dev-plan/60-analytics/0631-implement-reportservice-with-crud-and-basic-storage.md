# Reports · Add ReportService CRUD methods with ORM storage

| 元数据 | 值 |
|---|---|
| Issue | #631 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0632-add-reports-api-router-with-all-endpoints](../60-analytics/0632-add-reports-api-router-with-all-endpoints.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/services/report_service.py` currently only provides file-generation stubs (`generate_pdf_report`, `generate_excel_report`, `export_to_csv`) and a `schedule_report` upsert. The `reports` table (via `ReportModel` in `src/db/models/analytics.py`) has no CRUD service methods — reports cannot be listed, fetched, created, updated, or deleted through the service layer. Every downstream consumer (the router built in issue #632, analytics dashboards, scheduled exports) is blocked without these methods.

### 1.2 做完后

- **用户视角**: 无直接用户可见变化 — 纯底层 service 能力。
- **开发者视角**: `ReportService(session)` gains five new async methods: `list_reports`, `get_report`, `create_report`, `update_report`, `delete_report`. All return `ReportModel` ORM objects. Errors raise `NotFoundException` (404) or `ForbiddenException` (403).

### 1.3 不做什么（剔除）

- [ ] Exposing HTTP endpoints — handled by issue #632.
- [ ] File generation logic (PDF/Excel/CSV) — already present in existing service.
- [ ] Scheduling persistence — already present via `schedule_report` + `ReportScheduleModel`.
- [ ] Authorization beyond `tenant_id` enforcement (owner-level ACL is out of scope).

### 1.4 关键 KPI

- [ ] `ruff check src/services/report_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → all cases passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0 (no migration needed — table already exists via `ReportModel`)

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/services/report_service.py`](../../../src/services/report_service.py) L{1}-L{178}

The file already exists. Constructor takes `AsyncSession` and stores it as `self.session`. Current public methods: `generate_pdf_report`, `generate_excel_report`, `export_to_csv`, `schedule_report`. No CRUD methods for `reports` table.

```python
1:"""Report service — DB-backed schedule storage + file generation."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.report_schedule import ReportScheduleModel
from pkg.errors.app_exceptions import ValidationException

class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/report_service.py`](../../../src/services/report_service.py) — add five CRUD methods + exception imports
  - [`tests/unit/test_report_service.py`](../../tests/unit/test_report_service.py) — add unit tests for CRUD methods
- 要建：
  - 无

### 2.3 缺什么

- [ ] `list_reports(tenant_id, page, page_size) -> tuple[list[ReportModel], int]` — paginated listing with count
- [ ] `get_report(report_id, tenant_id) -> ReportModel` — single fetch with tenant isolation; raises `NotFoundException`
- [ ] `create_report(tenant_id, data) -> ReportModel` — insert new row with multi-tenant field
- [ ] `update_report(report_id, tenant_id, data) -> ReportModel` — partial update; raises `NotFoundException`
- [ ] `delete_report(report_id, tenant_id) -> None` — hard delete; raises `NotFoundException`
- [ ] Multi-tenant enforcement on all five methods (tenant isolation)
- [ ] Unit tests covering happy path + not-found + boundary cases

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无 | 无 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/report_service.py`](../../../src/services/report_service.py) | 新增 `list_reports`, `get_report`, `create_report`, `update_report`, `delete_report` 五个 async 方法；更新 import 添加 `NotFoundException`, `ForbiddenException`, `ReportModel`, `and_`, `select`, `update`, `delete` |
| [`tests/unit/test_report_service.py`](../../tests/unit/test_report_service.py) | 新增 CRUD 方法的单元测试：正常路径、report 不存在、tenant 隔离 |

### 3.3 新增能力

- **Service method**：`ReportService.list_reports(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[ReportModel], int]`
- **Service method**：`ReportService.get_report(self, report_id: int, tenant_id: int) -> ReportModel` — raises `NotFoundException`
- **Service method**：`ReportService.create_report(self, tenant_id: int, data: dict) -> ReportModel`
- **Service method**：`ReportService.update_report(self, report_id: int, tenant_id: int, data: dict) -> ReportModel` — raises `NotFoundException`
- **Service method**：`ReportService.delete_report(self, report_id: int, tenant_id: int) -> None` — raises `NotFoundException`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **ORM select vs raw SQL**: Use SQLAlchemy `select()` / `update()` / `delete()` from `sqlalchemy` — consistent with all other services in the codebase.
- **Pagination**: Use `LIMIT/OFFSET` via SQLAlchemy — consistent with `CustomerService.list_customers` and other services.
- **Partial update**: `update_report` accepts a `data: dict` and merges into existing row — not full replace, consistent with other services.

### 4.2 版本约束

N/A — no new dependencies introduced.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (enforced in service layer).
- Service returns ORM/model objects, **does not** call `.to_dict()` — serialization is the router's job.
- Service errors raise `AppException` subclasses (`NotFoundException`, `ForbiddenException`), **not** `ApiResponse.error()`.
- All five new methods are `async` and take `tenant_id: int` as a mandatory parameter.

### 4.4 已知坑

1. **`ReportModel` uses JSONB columns (`config`, `date_range`)** → SQLAlchemy `update()` with ORM objects requires assigning Python dicts directly, not raw JSON strings. → Mitigation: assign `existing.config = data.get("config", existing.config)` as a Python dict in the service.
2. **`ReportModel.__tablename__ = "reports"`** → ensure the table name does not conflict with SQL reserved words. "reports" is safe. → No mitigation needed.
3. **Unit test mock for `list_reports` needs count query** → the service calls two queries (COUNT + SELECT). The unit test mock must handle both. → Use the existing `make_count_handler` pattern from `conftest.py` or add a dedicated count handler.

---

## 5. 实现步骤（按顺序）

### Step 1: Add imports to report_service.py

在 [`src/services/report_service.py`](../../../src/services/report_service.py) 文件顶部，更新 import 块：

```python
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.analytics import ReportModel        # 新增
from db.models.report_schedule import ReportScheduleModel
from pkg.errors.app_exceptions import (            # 更新
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
```

**完成判定**：`ruff check src/services/report_service.py` → 0 errors

### Step 2: Add `list_reports` method

在 `ReportService` 类中添加：

```python
async def list_reports(
    self,
    tenant_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ReportModel], int]:
    """Return paginated reports for a tenant with total count."""
    offset = (max(1, page) - 1) * page_size

    count_result = await self.session.execute(
        select(func.count(ReportModel.id)).where(
            ReportModel.tenant_id == tenant_id
        )
    )
    total = count_result.scalar_one()

    result = await self.session.execute(
        select(ReportModel)
        .where(ReportModel.tenant_id == tenant_id)
        .order_by(ReportModel.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    reports = list(result.scalars().all())
    return reports, total
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_service import ReportService; import inspect; assert 'list_reports' in inspect.getmembers(ReportService, predicate=inspect.isfunction); print('ok')"` → exit 0

### Step 3: Add `get_report` method

在 `ReportService` 类中添加：

```python
async def get_report(self, report_id: int, tenant_id: int) -> ReportModel:
    """Fetch a single report, enforcing tenant isolation."""
    result = await self.session.execute(
        select(ReportModel).where(
            and_(
                ReportModel.id == report_id,
                ReportModel.tenant_id == tenant_id,
            )
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundException("Report")
    return report
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_service import ReportService; assert hasattr(ReportService, 'get_report'); print('ok')"` → exit 0

### Step 4: Add `create_report` method

在 `ReportService` 类中添加：

```python
async def create_report(
    self,
    tenant_id: int,
    data: dict[str, Any],
) -> ReportModel:
    """Insert a new report row for the given tenant."""
    now = datetime.now(UTC)
    report = ReportModel(
        tenant_id=tenant_id,
        name=data.get("name", "Unnamed Report"),
        type=data.get("type", "custom"),
        config=data.get("config", {}),
        date_range=data.get("date_range", {}),
        created_by=data.get("created_by", 0),
        last_run_at=None,
        created_at=now,
    )
    self.session.add(report)
    await self.session.flush()
    return report
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_service import ReportService; assert hasattr(ReportService, 'create_report'); print('ok')"` → exit 0

### Step 5: Add `update_report` method

在 `ReportService` 类中添加：

```python
async def update_report(
    self,
    report_id: int,
    tenant_id: int,
    data: dict[str, Any],
) -> ReportModel:
    """Partial update of a report; raises NotFoundException if missing or wrong tenant."""
    result = await self.session.execute(
        select(ReportModel).where(
            and_(
                ReportModel.id == report_id,
                ReportModel.tenant_id == tenant_id,
            )
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundException("Report")

    for field in ("name", "type", "config", "date_range", "last_run_at"):
        if field in data:
            setattr(report, field, data[field])
    report.updated_at = datetime.now(UTC)  # ReportModel has updated_at via server_default but we set explicitly

    await self.session.flush()
    await self.session.refresh(report)
    return report
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_service import ReportService; assert hasattr(ReportService, 'update_report'); print('ok')"` → exit 0

### Step 6: Add `delete_report` method

在 `ReportService` 类中添加：

```python
async def delete_report(self, report_id: int, tenant_id: int) -> None:
    """Hard-delete a report row; raises NotFoundException if missing or wrong tenant."""
    result = await self.session.execute(
        select(ReportModel.id).where(
            and_(
                ReportModel.id == report_id,
                ReportModel.tenant_id == tenant_id,
            )
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundException("Report")

    await self.session.execute(
        delete(ReportModel).where(
            and_(
                ReportModel.id == report_id,
                ReportModel.tenant_id == tenant_id,
            )
        )
    )
    await self.session.flush()
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_service import ReportService; assert hasattr(ReportService, 'delete_report'); print('ok')"` → exit 0

### Step 7: Write unit tests

在 [`tests/unit/test_report_service.py`](../../tests/unit/test_report_service.py)（新建文件）中添加测试用例：

```python
"""Unit tests for ReportService CRUD methods."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.report_service import ReportService
from pkg.errors.app_exceptions import NotFoundException
from tests.unit.conftest import MockState, make_mock_session


class TestListReports:
    def test_returns_reports_and_total(self):
        state = MockState()
        mock_session = make_mock_session([])  # add handlers below
        svc = ReportService(mock_session)
        # ... mock result, call list_reports, assert

    def test_pagination_offset(self):
        ...

    def test_empty_list_returns_zero_total(self):
        ...


class TestGetReport:
    def test_returns_report_for_valid_id(self):
        ...

    def test_raises_not_found_for_missing_id(self):
        with pytest.raises(NotFoundException):
            ...

    def test_raises_not_found_for_wrong_tenant(self):
        with pytest.raises(NotFoundException):
            ...


class TestCreateReport:
    def test_inserts_row_with_tenant_id(self):
        ...

    def test_sets_default_values(self):
        ...


class TestUpdateReport:
    def test_partial_update_preserves_unset_fields(self):
        ...

    def test_raises_not_found_for_missing_id(self):
        with pytest.raises(NotFoundException):
            ...


class TestDeleteReport:
    def test_deletes_existing_report(self):
        ...

    def test_raises_not_found_for_missing_id(self):
        with pytest.raises(NotFoundException):
            ...
```

Mock handlers must be added to `make_mock_session([...])` to simulate SQLAlchemy result objects. Use the pattern from other unit test files in `tests/unit/`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → all cases passed

---

## 6. 验收

- [ ] `ruff check src/services/report_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → all cases passed
- [ ] All five methods present on `ReportService`: `list_reports`, `get_report`, `create_report`, `update_report`, `delete_report`
- [ ] `get_report`, `update_report`, `delete_report` each raise `NotFoundException` when report_id is absent or belongs to another tenant
- [ ] `list_reports` returns `tuple[list[ReportModel], int]` with correct total count
- [ ] All methods enforce `tenant_id` in SQL WHERE clause

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ReportModel `updated_at` uses `server_default=func.now()` — ORM `flush()` may not auto-refresh it after `update_report` | 低 | 低 | Already guarded with explicit `report.updated_at = datetime.now(UTC)` in the method |
| Unit test mock setup complexity — `list_reports` fires two DB queries (count + select) | 低 | 中 | Add two separate mock handlers: one for count scalar, one for select scalars |
| `alembic` migration not needed — table already exists via `ReportModel` declaration | 低 | 低 | N/A — no migration to roll back; revert the code change |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/report_service.py tests/unit/test_report_service.py
git commit -m "feat(reports): add CRUD methods to ReportService (list/get/create/update/delete)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(reports): add ReportService CRUD with ORM storage" --body "Closes #631"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — `list_customers`, `get_customer`, `create_customer`, `update_customer` pattern
- 同类参考实现：[`src/services/sales_service.py`](../../../src/services/sales_service.py) — pagination + count pattern
- ORM model：[`src/db/models/analytics.py`](../../../src/db/models/analytics.py) — `ReportModel` definition
- 父 issue / 关联：#40
- 下游依赖：#632

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
