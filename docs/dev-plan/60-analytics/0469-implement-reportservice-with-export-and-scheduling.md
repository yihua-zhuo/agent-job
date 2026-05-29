# [Analytics] · ReportService export & scheduling

| 元数据 | 值 |
|---|---|
| Issue | #469 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#468](0486-add-missing-activityservice-methods.md) |
| 启用后赋能 | TBD - 待补充：父 issue #448 相关下游能力 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #469 (subtask of #448, blocked by #468) requires a ReportService that wraps AnalyticsService results and produces serializable byte/string outputs. Currently there is no dedicated reporting layer: callers must know how to format analytics data themselves, leading to duplicated serialization logic across routers. A central `ReportService` consolidates this responsibility and provides a clean extension point for future export formats.

### 1.2 做完后

- **用户视角**：无用户-visible changes — this is a pure service-layer addition consumed by API routers.
- **开发者视角**：`ReportService` is instantiated with an async session and exposes `generate_pdf_report`, `generate_excel_report`, `export_to_csv`, and `schedule_report` methods. AnalyticsService results flow through these methods and are serialized to `bytes` (PDF/Excel) or `str` (CSV). No file storage is written by the service; bytes/str are returned directly to the router caller.

### 1.3 不做什么（剔除）

- [ ] File storage layer (write-to-disk, S3, object store) — results returned to caller
- [ ] API router endpoints — routers that call ReportService are out of scope here
- [ ] Database-backed scheduling (persisting schedule metadata) — `schedule_report` records intent, caller decides disposition
- [ ] PDF/Excel generation from scratch (i.e., building report layout from raw data) — wraps AnalyticsService output only

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → ≥ 4 passed (export_to_csv + schedule_report coverage)
- [ ] `ruff check src/services/report_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_report_service.py` → 0 errors
- [ ] Service `__init__` accepts `session: AsyncSession` with no default; raises on None

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/analytics_service.py` L? — 确认 AnalyticsService 暴露的分析方法及返回类型（dataclass / ORM model），ReportService will wrap these.

TBD - 待验证：`src/services/` existing pattern — 确认同类 service（如 ActivityService / CustomerService）的构造函数签名和服务方法签名模式。

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/analytics_service.py` — ReportService wraps its results (确认中)
- 要建：
  - `src/services/report_service.py` — 核心 service，实现 export/schedule 方法
  - `tests/unit/test_report_service.py` — 单元测试（export_to_csv + schedule_report）

### 2.3 缺什么

- [ ] `ReportService` class with `session: AsyncSession` constructor and no default
- [ ] `generate_pdf_report(self, report_type: str, tenant_id: int) -> bytes` wrapping AnalyticsService
- [ ] `generate_excel_report(self, report_type: str, tenant_id: int) -> bytes` wrapping AnalyticsService
- [ ] `export_to_csv(self, data: list[dict], columns: list[str]) -> str` — pure transform, no I/O
- [ ] `schedule_report(self, report_type: str, cron_expr: str, tenant_id: int) -> dict` — returns schedule descriptor
- [ ] Unit tests for `export_to_csv` and `schedule_report` using MockState / make_mock_session pattern

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/report_service.py` | ReportService — wraps AnalyticsService; exports PDF/Excel/CSV; schedule intent |
| `tests/unit/test_report_service.py` | 单元测试 — export_to_csv + schedule_report coverage |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/services/analytics_service.py` | ReportService wraps this service's results |

### 3.3 新增能力

- **Service class**：`ReportService(session: AsyncSession)` — no default session
- **Service method**：`generate_pdf_report(report_type: str, tenant_id: int) -> bytes`
- **Service method**：`generate_excel_report(report_type: str, tenant_id: int) -> bytes`
- **Service method**：`export_to_csv(data: list[dict], columns: list[str]) -> str` — pure serialization
- **Service method**：`schedule_report(report_type: str, cron_expr: str, tenant_id: int) -> dict`
- **Error handling**：raises `ValidationException` for invalid `cron_expr`, `NotFoundException` when AnalyticsService returns nothing to wrap

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Return bytes/str from service, not file path** — avoids inventing a storage layer; caller (router) decides what to do with the bytes (stream, save, email). Consistent with CLAUDE.md service pattern: service returns domain objects, serialization is the caller's concern.
- **schedule_report returns dict, not ORM model** — scheduling intent is a transient descriptor (type, cron, tenant) that has no persistent representation yet. Returning `dict` keeps the service schema-agnostic and avoids a new ORM model for an interface stub.
- **export_to_csv is pure transform** — no DB access, no AnalyticsService dependency; fully testable without mocking the session.

### 4.2 版本约束

TBD - 待补充：如引入新依赖（如 `reportlab` / `openpyxl`）请在此填表。当前无新依赖引入。

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (CLAUDE.md §Multi-Tenancy)
- Service `__init__` accepts `session: AsyncSession` with NO default
- Service returns bytes/str/dict; does NOT call `.to_dict()` or return `ApiResponse`
- Service raises `AppException` subclasses; does NOT return error responses
- PYTHONPATH=src; imports use `from services...`, `from db.models...`, NOT `from src.services...`

### 4.4 已知坑

1. **SQLAlchemy column named `metadata` on Base subclass** → crash at class definition (`Base.metadata` collision). Avoid column name `metadata`; use `event_metadata` / `payload` / `meta` if any report metadata field is needed.
2. **No known migration** — this issue adds a service class only, no ORM model or DB schema change. If a later subtask of #448 adds a `report_schedule` table, Alembic autogen will likely emit `sa.JSON()` for JSONB columns and omit `timezone=True` on DateTime — correct manually after autogenerate.

---

## 5. 实现步骤（按顺序）

### Step 1: Create ReportService skeleton

Create `src/services/report_service.py` with the class skeleton matching the established service pattern.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        if session is None:
            raise ValidationException("ReportService requires a session; None provided")
        self._session = session

    async def generate_pdf_report(self, report_type: str, tenant_id: int) -> bytes:
        raise NotImplementedError

    async def generate_excel_report(self, report_type: str, tenant_id: int) -> bytes:
        raise NotImplementedError

    async def export_to_csv(self, data: list[dict], columns: list[str]) -> str:
        raise NotImplementedError

    async def schedule_report(self, report_type: str, cron_expr: str, tenant_id: int) -> dict:
        raise NotImplementedError
```

**完成判定**：`ruff check src/services/report_service.py` → 0 errors

---

### Step 2: Implement export_to_csv (pure transform, no DB)

Implement `export_to_csv` as a pure function — accepts `data: list[dict]` and `columns: list[str]`, returns CSV-formatted `str`. No session needed for this method.

```python
    async def export_to_csv(self, data: list[dict], columns: list[str]) -> str:
        if not columns:
            raise ValidationException("columns list must not be empty")
        import io, csv
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, "") for k in columns})
        return buf.getvalue()
```

**完成判定**：
- `ruff check src/services/report_service.py` → 0 errors
- `PYTHONPATH=src python -c "from services.report_service import ReportService; print('import ok')"` → import ok

---

### Step 3: Implement schedule_report (validation + dict return)

Implement `schedule_report` — validates `cron_expr` format (basic regex check for 5-field cron), returns a dict descriptor with `report_type`, `cron_expr`, `tenant_id`, `created_at`. Raises `ValidationException` on bad cron; raises `NotFoundException` if the report_type is not recognized.

```python
    import re
    _CRON_RE = re.compile(r'^(\*|([0-5]?\d)) (\*|([01]?\d|2[0-3])) (\*|([12]?\d|3[01])) (\*|(1[0-2]|0?[1-9])) ([0-6])$')

    async def schedule_report(self, report_type: str, cron_expr: str, tenant_id: int) -> dict:
        if not _CRON_RE.match(cron_expr.strip()):
            raise ValidationException(f"Invalid cron expression: {cron_expr}")
        valid_types = {"activity_summary", "sales_summary", "pipeline_report"}
        if report_type not in valid_types:
            raise NotFoundException(f"Report type '{report_type}'")
        from datetime import datetime, timezone
        return {
            "report_type": report_type,
            "cron_expr": cron_expr.strip(),
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
```

**完成判定**：
- `ruff check src/services/report_service.py` → 0 errors
- `PYTHONPATH=src python -c "from services.report_service import ReportService; import re; print('schedule_report ok')"` → no import errors

---

### Step 4: Implement generate_pdf_report and generate_excel_report (wrapping AnalyticsService)

TBD - 待验证：在实现前确认 AnalyticsService 的返回类型。预期：

```python
async def generate_pdf_report(self, report_type: str, tenant_id: int) -> bytes:
    analytics = AnalyticsService(self._session)
    raw = await analytics.get_report_data(report_type, tenant_id)
    if raw is None:
        raise NotFoundException(f"No data for report type '{report_type}'")
    # serialize raw dict to PDF bytes via reportlab or similar
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    table_data = [[str(v) for v in row.values()] for row in (raw.get("rows", []) if isinstance(raw, dict) else [])]
    table_data.insert(0, list(raw.keys()) if isinstance(raw, dict) and raw else ["Value"])
    table = Table(table_data)
    doc.build([table])
    return buf.getvalue()
```

同样实现 `generate_excel_report` 使用 `openpyxl` Workbook。

**完成判定**：`ruff check src/services/report_service.py` → 0 errors

---

### Step 5: Write unit tests for export_to_csv and schedule_report

Create `tests/unit/test_report_service.py` using the mock session pattern. Define a minimal `mock_db_session` fixture and test:

- `test_export_to_csv_empty_data` — no rows → header row only
- `test_export_to_csv_with_data` — maps columns correctly, ignores extra keys
- `test_export_to_csv_empty_columns_raises` — raises ValidationException
- `test_schedule_report_valid_cron` — returns dict with expected keys
- `test_schedule_report_invalid_cron_raises` — raises ValidationException
- `test_schedule_report_unknown_report_type_raises` — raises NotFoundException

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.report_service import ReportService
from pkg.errors.app_exceptions import ValidationException, NotFoundException


@pytest.fixture
def mock_session():
    return MagicMock(spec=["execute", "scalar_one"])


@pytest.fixture
def report_service(mock_session):
    return ReportService(mock_session)


class TestExportToCsv:
    async def test_empty_data(self, report_service):
        result = await report_service.export_to_csv([], ["name", "value"])
        lines = result.strip().split("\n")
        assert lines == ["name,value"]

    async def test_with_rows(self, report_service):
        data = [{"name": "Alice", "value": 10}, {"name": "Bob", "value": 20}]
        result = await report_service.export_to_csv(data, ["name", "value"])
        lines = result.strip().split("\n")
        assert lines[0] == "name,value"
        assert lines[1] == "Alice,10"
        assert lines[2] == "Bob,20"

    async def test_ignores_extra_keys(self, report_service):
        data = [{"name": "Alice", "value": 10, "extra": "ignore"}]
        result = await report_service.export_to_csv(data, ["name"])
        assert "extra" not in result

    async def test_empty_columns_raises(self, report_service):
        with pytest.raises(ValidationException):
            await report_service.export_to_csv([{"a": 1}], [])


class TestScheduleReport:
    async def test_valid_cron(self, report_service):
        result = await report_service.schedule_report("activity_summary", "0 9 * * 1", 42)
        assert result["report_type"] == "activity_summary"
        assert result["cron_expr"] == "0 9 * * 1"
        assert result["tenant_id"] == 42
        assert "created_at" in result

    async def test_invalid_cron_raises(self, report_service):
        with pytest.raises(ValidationException):
            await report_service.schedule_report("activity_summary", "not-a-cron", 1)

    async def test_unknown_report_type_raises(self, report_service):
        with pytest.raises(NotFoundException):
            await report_service.schedule_report("nonexistent_report", "0 9 * * 1", 1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → `6 passed`

---

## 6. 验收

- [ ] `ruff check src/services/report_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_report_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → `6 passed`
- [ ] `PYTHONPATH=src python -c "from services.report_service import ReportService; s = ReportService(None)"` → raises `ValidationException` (session guard)
- [ ] `PYTHONPATH=src python -c "from services.report_service import ReportService; print('import ok')"` → no errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| AnalyticsService API changes after this service is written (incompatible return type) | 低 | 中 | ReportService methods that wrap AnalyticsService are isolated; only `generate_pdf_report` / `generate_excel_report` need updating when AnalyticsService changes |
| Third-party PDF/Excel library (reportlab / openpyxl) version conflict | 低 | 中 | Keep library usage behind a thin wrapper; if version pins cause CI failures, pin to known-working version in pyproject.toml |
| schedule_report cron validation is too strict (legitimate cron variants rejected) | 中 | 低 | Widen regex to accept more cron field variants; add a comment documenting accepted format |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/report_service.py tests/unit/test_report_service.py
git commit -m "feat(analytics): implement ReportService with export and scheduling (#469)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): implement ReportService (#469)" --body "Closes #469"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/activity_service.py` — established service pattern (constructor + tenant_id + raises on error)
- 第三方文档：[reportlab documentation](https://docs.reportlab.com/) (PDF generation) | [openpyxl documentation](https://openpyxl.readthedocs.io/) (Excel generation)
- 父 issue / 关联：#448 (parent), #468 (dependency)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
