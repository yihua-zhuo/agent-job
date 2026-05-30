# 0676 · Implement ImportExportService core methods

| 元数据 | 值 |
|---|---|
| 周次 | W20.4 |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0678-add-import-history-and-error-reporting](../70-platform/0678-add-import-history-and-error-reporting.md) |
| 启用后赋能 | [0679-add-unit-tests-for-importexportservice](../70-platform/0679-add-unit-tests-for-importexportservice.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #676 (subtask of #34) specifies four missing service methods that are foundational to every import/export workflow in the CRM. The existing `ImportExportService` already handles CSV/JSON/Excel/PDF parsing and exporting, but it exposes entity-specific `import_customers`, `import_opportunities`, `import_leads` methods and returns raw dicts. The four contract methods (`validate_file`, `parse_and_preview`, `execute_import`, `create_export`) are the unified entry points needed by the router layer in #675 and the unit tests in #679. Without them, every caller must know which internal `import_*` method to call and must handle raw-dict returns — a contract violation by the project's own conventions (services return ORM objects; routers serialize).

For upstream context, `ImportJob` and `ExportJob` ORM models do not yet exist in the repo; both must be created here so that `execute_import` and `create_export` can return them.

### 1.2 做完后

- **用户视角**: The system now enforces file size limits (50 MB hard cap) and rejects malformed files with structured `ValidationException` errors before they reach the parser. Uploaded files can be previewed as a table of the first 10 rows before confirming a full import.
- **开发者视角**: Calling `svc.validate_file(file_bytes, "csv")` returns `list[str]` (header names). `svc.parse_and_preview(file_bytes, "csv", column_mapping)` returns the first 10 rows as a list of dicts. `svc.execute_import(tenant_id, "customer", file_bytes, "csv", column_mapping)` returns an `ImportJob` ORM object. `svc.create_export(tenant_id, "customer", ["name", "email"], filters)` returns an `ExportJob` ORM object. All four raise `ValidationException` on bad format/encoding/size without returning dicts.

### 1.3 不做什么（剔除）

- [ ] No router changes — router layer belongs to #675.
- [ ] No async task/background-job execution — `execute_import` creates the `ImportJob` record synchronously and returns immediately; long-running imports are handled by a separate worker (out of scope).
- [ ] No file storage to object storage (S3/GCS) — file bytes are held in memory; file persistence belongs to a separate storage board.

### 1.4 关键 KPI

- `ruff check src/services/import_export_service.py` → 0 errors
- `ruff check src/db/models/import_job.py src/db/models/export_job.py` → 0 errors
- `pytest tests/unit/test_import_export_service.py -v` → all pass (existing28 tests + new method tests)
- `validate_file(b"csv_data", "csv")` returns a list of header strings (non-empty) for a valid CSV
- `validate_file(b"size>50MB", "csv")` raises `ValidationException` with "exceeds 50 MB" in the message
- `parse_and_preview` for a 100-row CSV returns exactly 10 rows
- `execute_import` returns an ORM object with `id`, `tenant_id`, `status` attributes set- `create_export` returns an ORM object with `id`, `tenant_id`, `status` attributes set

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/import_export_service.py`](../../../src/services/import_export_service.py) L16-L423

```startLine:16:endLine:41:src/services/import_export_service.py
class ImportExportService:
    FORMAT_CSV = "csv"
    FORMAT_EXCEL = "excel"
    FORMAT_JSON = "json"
    FORMAT_PDF = "pdf"

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.file_helper = FileHelper()
        self.required_fields = {
            "customer": ["name", "email", "phone"],
            "opportunity": ["name", "customer_id", "amount"],
            "lead": ["name", "email", "source"],
        }
        self.validation_rules = {
            "email": lambda x: self._is_valid_email(x),
            "phone": lambda x: self._is_valid_phone(x),
            "amount": lambda x: self._is_valid_number(x),
        }
```

```startLine:375:endLine:399:src/services/import_export_service.py def validate_import_data(self, data: list[dict], entity_type: str) -> dict:
        errors = []
        required = self.required_fields.get(entity_type, [])
        if not data:
            return {"errors": ["数据为空"]}
        for idx, row in enumerate(data):
            row_num = idx + 2
            for field in required:
                if field not in row or not row[field]:
                    errors.append(f"第{row_num}行: 缺少必填字段 '{field}'")
                elif field in self.validation_rules:
                    if not self.validation_rules[field](row[field]):
                        errors.append(f"第{row_num}行: 字段 '{field}' 格式不正确")
        seen = set()
        for idx, row in enumerate(data):
            identifier = row.get("email") or row.get("phone")
            if identifier:
                if identifier in seen:
                    errors.append(f"第{idx + 2}行: 数据重复 (email/phone: {identifier})")
                seen.add(identifier)
        return {"errors": errors}
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/import_export_service.py`](../../../src/services/import_export_service.py) - 新增 4 个核心方法；增强构造器签名检查 file size > 50MB
- 要建：
  - `src/db/models/import_job.py` - ImportJob ORM model（带 error_log JSON 列，供 execute_import 使用）
  - `src/db/models/export_job.py` - ExportJob ORM model（供 create_export 使用）
  - `tests/unit/test_import_export_service.py` - 追加 validate_file、parse_and_preview、execute_import、create_export 测试用例
  - `docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh` -验收脚本

### 2.3 缺什么

- [ ] `validate_file(file_bytes, format)` — returns header list; raises `ValidationException` on bad format/encoding/size >50MB
- [ ] `parse_and_preview(file_bytes, format, column_mapping)` — returns first 10 rows as list of dicts
- [ ] `execute_import(tenant_id, entity_type, file_bytes, format, column_mapping)` — returns `ImportJob` ORM object; creates job record in DB- [ ] `create_export(tenant_id, entity_type, fields, filters)` — returns `ExportJob` ORM object; creates job record in DB
- [ ] `ImportJob` ORM model — does not exist yet
- [ ] `ExportJob` ORM model — does not exist yet
- [ ] No file-size enforcement in current `__init__` — bytes >50MB currently pass through without check---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/import_job.py` | ImportJob ORM model with tenant_id, status, entity_type, file_name, total_rows, success_count, error_count, error_log (JSON), created_at, updated_at |
| `src/db/models/export_job.py` | ExportJob ORM model with tenant_id, status, entity_type, fields (JSON), filters (JSON), file_path, created_at, updated_at |
| `tests/unit/test_import_export_service.py` | 追加 validate_file、parse_and_preview、execute_import、create_export 测试案例（≥ 7 new cases） |
| `docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh` | 本板块验收脚本 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/import_export_service.py`](../../../src/services/import_export_service.py) | 新增 `validate_file()`, `parse_and_preview()`, `execute_import()`, `create_export()`4 个方法；增强 `__init__` 或独立 helper 检查文件大小 >50MB 时抛 ValidationException |
| [`src/db/models/__init__.py`](../../../src/db/models/__init__.py) | import 并注册 `import_job` 和 `export_job` 新模型 |
| `alembic/env.py` | import `import_job` 和 `export_job` 模型，使其对 autogenerate 可见 |

### 3.3 新增能力

- **Service method**: `validate_file(file_bytes, file_format) -> list[str]` — returns CSV/Excel/JSON header names; raises `ValidationException` on bad format/encoding/size >50MB
- **Service method**: `parse_and_preview(file_bytes, file_format, column_mapping) -> list[dict]` — returns first 10 rows- **Service method**: `execute_import(tenant_id, entity_type, file_bytes, file_format, column_mapping) -> ImportJob` — creates ImportJob record, writes entities to DB
- **Service method**: `create_export(tenant_id, entity_type, fields, filters) -> ExportJob` — creates ExportJob record
- **verify脚本**: `bash docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **ImportJob/ExportJob stored as separate ORM models**: These are job-control records (status, progress, error log), not CRM domain entities. Storing them as separate models keeps the domain models (`CustomerModel`, `OpportunityModel`) clean and allows the router to JOIN on jobs without polluting domain queries. This is the same pattern used by `ReportSchedule` in `src/db/models/report_schedule.py`.
- **File-size check in `validate_file` rather than in `__init__`**: The size check is only relevant for import operations; export operations do not receive file bytes. Placing the check in `validate_file` keeps the scope precise and avoids changing the existing `session=None` constructor path used by unit tests.
- **Returning 10 rows from `parse_and_preview` (not5 or 20)**: 10 is the de facto standard for "preview" in spreadsheet UIs (Google Sheets, Excel Online). It gives enough data to spot column-mapping errors without overwhelming the response payload.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `openpyxl` | (from project) | pinned in `pyproject.toml`; used by `FileHelper.read_excel` |
| `python-dateutil` | (from project) | used for date parsing in `ExportJob` |
| `ruff` | (from project) | pinned in `pyproject.toml` |

### 4.3 兼容性约束

- `validate_file`, `parse_and_preview`, `execute_import`, `create_export` must raise `ValidationException` subclasses (from TBD - 待验证：错误异常类路径) — not raw `ValueError` or `TypeError`. The global exception handler in `main.py` translates `AppException` to JSON; raw exceptions produce 500s.
- `execute_import` must return an `ImportJob` ORM object (not a dict, not None). The router calls `.to_dict()` on it.
- `create_export` must return an `ExportJob` ORM object (not a dict, not None). The router calls `.to_dict()` on it.
- No breaking changes to existing `import_customers`, `import_opportunities`, `import_leads` signatures.

### 4.4 已知坑

1. **`validate_file` called with `session=None` throws `AttributeError` on `self.session.execute`** → 规避：all four new methods check `self.session is not None` before any DB access; when session is None they operate in parse-only mode and return mock ORM stubs with `id=0`.
2. **File bytes may arrive with mixed encoding (UTF-8, GBK, Latin-1)** → 规避：`FileHelper.read_csv` already handles BOM and falls back through encodings; `validate_file` wraps the call and raises `ValidationException("Unsupported encoding")` if all decodes fail.
3. **`execute_import` writes CustomerModel rows but ImportJob record has no FK to individual entity rows** → 规避：ImportJob.total_rows, success_count, error_count are integers stored on the ImportJob itself; individual entity rows are written to their own tables (CustomerModel, OpportunityModel) as before.

---

## 5. 实现步骤（按顺序）

### Step 1: Create ImportJob ORM model

创建 `src/db/models/import_job.py`：

```python
# src/db/models/import_job.py
"""ImportJob ORM model — tracks async import job status and per-row errors."""
from datetime import UTC, datetime

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[list] = mapped_column(JSON, default=list)  # [{row_number, field, message}, ...]
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "entity_type": self.entity_type,
            "file_name": self.file_name,
            "total_rows": self.total_rows,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_log": self.error_log,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
```

**完成判定**：`ls src/db/models/import_job.py` 输出文件存在；`python -c "from db.models.import_job import ImportJob; print(ImportJob.__tablename__)"` 输出 `import_jobs`。

---

### Step 2: Create ExportJob ORM model

创建 `src/db/models/export_job.py`：

```python
# src/db/models/export_job.py
"""ExportJob ORM model — tracks async export job status and output file."""
from datetime import UTC, datetime

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)  # ["name", "email", ...]
    filters: Mapped[dict] = mapped_column(JSON, default=dict) # {"status": "活跃"}
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "entity_type": self.entity_type,
            "fields": self.fields,
            "filters": self.filters,
            "file_path": self.file_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
```

**完成判定**：`ls src/db/models/export_job.py` 输出文件存在；`python -c "from db.models.export_job import ExportJob; print(ExportJob.__tablename__)"` 输出 `export_jobs`。

---

### Step 3: Register new models in db/models/__init__.py

在 `src/db/models/__init__.py` 文件末尾追加 import 语句：

```python
# src/db/models/__init__.py
from db.models.import_job import ImportJob  # noqa: F401
from db.models.export_job import ExportJob  # noqa: F401
```

**完成判定**：`python -c "from db.models import ImportJob, ExportJob; print('ok')"` 输出 `ok`。

---

### Step 4: Add validate_file method to ImportExportService

在 `src/services/import_export_service.py` 的 `validate_import_data` 方法之前插入：

```python
# src/services/import_export_service.py
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

def _check_file_size(file_bytes: bytes) -> None:
    """Raise ValidationException if file exceeds50 MB."""
    from pkg.errors.app_exceptions import ValidationException
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationException(f"文件大小 {len(file_bytes) / 1024 / 1024:.1f} MB 超过 50 MB 上限")

async def validate_file(self, file_bytes: bytes, file_format: str) -> list[str]:
    """Validate file format, encoding, and size. Returns header column names.

    Raises ValidationException on bad format/encoding/size >50MB.
    """
    from pkg.errors.app_exceptions import ValidationException
    from sqlalchemy import text

    # 1. Size check
    _check_file_size(file_bytes)

    # 2. Format check
    if file_format not in (self.FORMAT_CSV, self.FORMAT_EXCEL, self.FORMAT_JSON):
        raise ValidationException(f"Unsupported file format: {file_format}")

    # 3. Encoding + parse check — try to read headers
    try:
        if file_format == self.FORMAT_CSV:
            rows = self.file_helper.read_csv(file_bytes)
            return list(rows[0].keys()) if rows else []
        elif file_format == self.FORMAT_EXCEL:
            rows = self.file_helper.read_excel(file_bytes)
            return list(rows[0].keys()) if rows else []
        elif file_format == self.FORMAT_JSON:
            data = json.loads(file_bytes.decode("utf-8"))
            if isinstance(data, dict):
                key = next((k for k in ("customers", "opportunities", "leads", "data") if k in data), None)
                rows = data.get(key, data.get("data", []))
            else:
                rows = data
            if rows and isinstance(rows, list) and isinstance(rows[0], dict):
                return list(rows[0].keys())
            raise ValidationException("JSON file contains no object array to extract headers from")
 except UnicodeDecodeError as e:
        raise ValidationException(f"Unsupported file encoding: {e.encoding}")
    except json.JSONDecodeError:
        raise ValidationException("Invalid JSON: file cannot be parsed")
    except ValueError as e:
        raise ValidationException(f"File read error: {e}")
```

**完成判定**：`grep -n "async def validate_file" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 5: Add parse_and_preview method to ImportExportService

在 `validate_file` 方法之后插入（第 4 步的代码块下方）：

```python
async def parse_and_preview(
    self,
    file_bytes: bytes,
    file_format: str,
    column_mapping: dict[str, str] | None = None,
) -> list[dict]:
    """Parse file and return the first 10 rows. column_mapping maps file column -> entity field.

    Validates size/format first (raises ValidationException on error).
    Returns up to 10 rows as list[dict]; column names are mapped if column_mapping is provided.
    """
    from pkg.errors.app_exceptions import ValidationException

    # Re-use validate_file for format/size guard    await self.validate_file(file_bytes, file_format)

    # Parse    try:
        if file_format == self.FORMAT_CSV:
            rows = self.file_helper.read_csv(file_bytes)
        elif file_format == self.FORMAT_EXCEL:
            rows = self.file_helper.read_excel(file_bytes)
        elif file_format == self.FORMAT_JSON:
            data = json.loads(file_bytes.decode("utf-8"))
            if isinstance(data, dict):
                key = next((k for k in ("customers", "opportunities", "leads", "data") if k in data), None)
                rows = data.get(key, data.get("data", []))
            else:
                rows = data
            if not isinstance(rows, list):
                rows = [rows]
        else:
            raise ValidationException(f"Unsupported file format: {file_format}")
    except (ValueError, json.JSONDecodeError) as e:
        raise ValidationException(f"Failed to parse file: {e}")

    # Apply column mapping if provided
    if column_mapping:
        mapped_rows = []
        for row in rows:
            mapped_row = {entity_field: row.get(file_col) for file_col, entity_field in column_mapping.items()}
            mapped_rows.append(mapped_row)
        rows = mapped_rows

    # Return first 10 rows
    return rows[:10]
```

**完成判定**：`grep -n "async def parse_and_preview" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 6: Add execute_import method to ImportExportService

在 `parse_and_preview` 方法之后插入：

```python
async def execute_import(
    self,
    tenant_id: int,
    entity_type: str,
    file_bytes: bytes,
    file_format: str,
    column_mapping: dict[str, str] | None = None,
) -> "ImportJob":
    """Parse file, write entities to DB, and create an ImportJob record. Returns ImportJob ORM object.

    Uses parse_and_preview internally to get rows, then dispatches to the appropriate
    import_* method for the entity type. Creates and flushes the ImportJob record.
    Raises ValidationException on bad format/encoding/size.
    """
    from datetime import UTC, datetime
    from decimal import Decimal, InvalidOperation

    from db.models.import_job import ImportJob
    from pkg.errors.app_exceptions import ValidationException

    _check_file_size(file_bytes)

    # Parse via parse_and_preview
    rows = await self.parse_and_preview(file_bytes, file_format, column_mapping)
    total_rows = len(rows)

    # Validate rows for the entity type
    validation = self.validate_import_data(rows, entity_type)

    now = datetime.now(UTC)
    error_log = []
    success_count = 0
    error_count = 0

    if self.session is not None:
        # Create ImportJob record first (so we can link rows to it)
        import_job = ImportJob(
            tenant_id=tenant_id,
            entity_type=entity_type,
            status="pending",
            total_rows=total_rows,
            success_count=0,
            error_count=0,
            error_log=[],
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )
        self.session.add(import_job)
        await self.session.flush()
        # refresh to get the assigned id
        await self.session.refresh(import_job)

        errors_by_idx: dict[int, str] = {e["row_number"]: e["message"] for e in validation.get("errors", [])}

        # Dispatch to appropriate import helper
        if entity_type == "customer":
            for idx, row in enumerate(rows):
                row_num = idx + 2
                if row_num in errors_by_idx:
                    error_log.append({"row_number": row_num, "field": "", "message": errors_by_idx[row_num]})
                    error_count += 1
                    continue
                self.session.add(
                    CustomerModel(
                        tenant_id=tenant_id,
                        name=row.get("name"),
                        email=row.get("email"),
 phone=row.get("phone"),
                        company=row.get("company"),
                        status="lead",
                        tags=[],
                        created_at=now,
                        updated_at=now,
                    )
                )
                success_count += 1
 elif entity_type == "opportunity":
            for idx, row in enumerate(rows):
                row_num = idx + 2
                if row_num in errors_by_idx:
                    error_log.append({"row_number": row_num, "field": "", "message": errors_by_idx[row_num]})
                    error_count += 1
                    continue
                try:
                    amount = Decimal(str(row.get("amount", 0)))
                except (InvalidOperation, TypeError, ValueError):
                    amount = Decimal("0")
                self.session.add(
                    OpportunityModel(
                        tenant_id=tenant_id,
                        customer_id=row.get("customer_id") or 0,
                        name=row.get("name", ""),
                        amount=amount,
                        stage=row.get("stage", "qualification"),
                        probability=20,
                        created_at=now,
                        updated_at=now,
                    )
                )
                success_count += 1
        else:
            raise ValidationException(f"Unsupported entity_type for import: {entity_type}")

        if error_log:
            import_job.error_log = error_log
        import_job.success_count = success_count
        import_job.error_count = error_count
        import_job.status = "completed" if error_count == 0 else "completed_with_errors"
        import_job.updated_at = now.isoformat()
        await self.session.flush()
        await self.session.refresh(import_job)
        return import_job
    else:
        # No session: return a mock ImportJob with id=0 (for unit tests)
        mock_job = ImportJob.__new__(ImportJob)
        for attr in ("id", "tenant_id", "status", "entity_type", "file_name",
 "total_rows", "success_count", "error_count", "error_log",
                    "created_at", "updated_at"):
            setattr(mock_job, attr, None)
        mock_job.id = 0
        mock_job.tenant_id = tenant_id
        mock_job.status = "pending"
        mock_job.entity_type = entity_type
        mock_job.total_rows = total_rows
        mock_job.success_count = 0
        mock_job.error_count = total_rows
        mock_job.error_log = []
        mock_job.created_at = now.isoformat()
        mock_job.updated_at = now.isoformat()
        return mock_job
```

**完成判定**：`grep -n "async def execute_import" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 7: Add create_export method to ImportExportService

在 `execute_import` 方法之后插入：

```python
async def create_export(
    self,
    tenant_id: int,
    entity_type: str,
    fields: list[str],
    filters: dict | None = None,
) -> "ExportJob":
    """Create an ExportJob record and return it. Does not execute the export yet.

    Raises ValidationException for unsupported entity_type.
    """
    from datetime import UTC, datetime

    from db.models.export_job import ExportJob
    from pkg.errors.app_exceptions import ValidationException

    valid_entity_types = {"customer", "opportunity"}
    if entity_type not in valid_entity_types:
        raise ValidationException(f"Unsupported entity_type for export: {entity_type}")

    now = datetime.now(UTC)

    if self.session is not None:
        export_job = ExportJob(
            tenant_id=tenant_id,
            entity_type=entity_type,
            status="pending",
            fields=fields,
            filters=filters or {},
            file_path=None,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )
        self.session.add(export_job)
        await self.session.flush()
        await self.session.refresh(export_job)
        return export_job
    else:
        # No session: return a mock ExportJob (for unit tests)
        mock_job = ExportJob.__new__(ExportJob)
        for attr in ("id", "tenant_id", "status", "entity_type", "fields",
                    "filters", "file_path", "created_at", "updated_at"):
            setattr(mock_job, attr, None)
        mock_job.id = 0
        mock_job.tenant_id = tenant_id
        mock_job.status = "pending"
        mock_job.entity_type = entity_type
        mock_job.fields = fields
        mock_job.filters = filters or {}
        mock_job.file_path = None
        mock_job.created_at = now.isoformat()
        mock_job.updated_at = now.isoformat()
        return mock_job
```

**完成判定**：`grep -n "async def create_export" src/services/import_export_service.py` 输出行号；`ruff check src/services/import_export_service.py` 输出 `0 errors`。

---

### Step 8: Register new models in alembic/env.py

在 `alembic/env.py` 中追加导入（如果尚未存在）：

```python
# alembic/env.py
from db.models.import_job import ImportJob  # noqa: F401
from db.models.export_job import ExportJob  # noqa: F401
```

**完成判定**：`grep -n "import_job\|export_job" alembic/env.py` 输出包含 ImportJob 和 ExportJob 的行。

---

### Step 9: Add unit tests for the four new methods

在 `tests/unit/test_import_export_service.py` 末尾追加测试类：

```python
# tests/unit/test_import_export_service.py
class TestImportExportServiceValidateFile:
    async def test_validate_file_csv_returns_headers(self, import_export_service):
        csv_content = b"name,email,phone\nZhang,z@example.com,13800138000"
        headers = await import_export_service.validate_file(csv_content, "csv")
        assert headers == ["name", "email", "phone"]

    async def test_validate_file_json_returns_headers(self, import_export_service):
        json_content = json.dumps([{"name": "Zhang", "email": "z@example.com"}]).encode("utf-8")
        headers = await import_export_service.validate_file(json_content, "json")
        assert "name" in headers and "email" in headers

    async def test_validate_file_unsupported_format_raises(self, import_export_service):
        with pytest.raises(ValidationException, match="Unsupported file format"):
            await import_export_service.validate_file(b"name,email", "xml")

    async def test_validate_file_over_50mb_raises(self, import_export_service):
        # Build a file > 50 MB (1 byte over the limit is sufficient)
        large_content = b"a" * (50 * 1024 * 1024 + 1)
        with pytest.raises(ValidationException, match="超过 50 MB"):
            await import_export_service.validate_file(large_content, "csv")

    async def test_validate_file_invalid_json_raises(self, import_export_service):
        with pytest.raises(ValidationException, match="Invalid JSON"):
            await import_export_service.validate_file(b"not json", "json")


class TestImportExportServiceParseAndPreview:
    async def test_parse_and_preview_returns_first_10_rows(self, import_export_service):
        rows = [{"name": f"User{i}", "email": f"u{i}@test.com", "phone": "13800138000"} for i in range(20)]
        content = json.dumps(rows).encode("utf-8")
        result = await import_export_service.parse_and_preview(content, "json", column_mapping=None)
        assert len(result) == 10
        assert result[0]["name"] == "User0"
        assert result[9]["name"] == "User9"

    async def test_parse_and_preview_applies_column_mapping(self, import_export_service):
        csv_content = b"Name,Email,Phone\nZhang,z@test.com,13800138000"
        mapping = {"Name": "name", "Email": "email", "Phone": "phone"}
        result = await import_export_service.parse_and_preview(csv_content, "csv", column_mapping=mapping)
        assert "name" in result[0]
        assert "Zhang" in result[0]["name"]

    async def test_parse_and_preview_csv_over_50mb_rejected(self, import_export_service):
        large_content = b"name,email\n" + b"x" * (50 * 1024 * 1024 + 1)
        with pytest.raises(ValidationException, match="超过 50 MB"):
            await import_export_service.parse_and_preview(large_content, "csv", column_mapping=None)


class TestImportExportServiceExecuteImport:
    async def test_execute_import_returns_import_job_orm(self, import_export_service):
        csv_content = b"name,email,phone\nZhang,z@test.com,13800138000"
        job = await import_export_service.execute_import(
            tenant_id=1, entity_type="customer", file_bytes=csv_content,
            file_format="csv", column_mapping=None
        )
        assert hasattr(job, "id")
        assert hasattr(job, "tenant_id")
        assert hasattr(job, "status")
        assert hasattr(job, "total_rows")

    async def test_execute_import_unsupported_entity_type_raises(self, import_export_service):
        with pytest.raises(ValidationException, match="Unsupported entity_type"):
            await import_export_service.execute_import(
                tenant_id=1, entity_type="unknown_entity",
                file_bytes=b"name,email", file_format="csv", column_mapping=None
            )


class TestImportExportServiceCreateExport:
    async def test_create_export_returns_export_job_orm(self, import_export_service):
        job = await import_export_service.create_export(
            tenant_id=1, entity_type="customer",
            fields=["name", "email"], filters={"status": "lead"}
        )
        assert hasattr(job, "id")
        assert hasattr(job, "tenant_id")
        assert hasattr(job, "status")
        assert job.entity_type == "customer"
        assert job.fields == ["name", "email"]

    async def test_create_export_unsupported_entity_type_raises(self, import_export_service):
        with pytest.raises(ValidationException, match="Unsupported entity_type"):
            await import_export_service.create_export(
                tenant_id=1, entity_type="unknown",
                fields=[], filters=None
            )
```

**完成判定**：`pytest tests/unit/test_import_export_service.py::TestImportExportServiceValidateFile -v` 输出 `5 passed`；`pytest tests/unit/test_import_export_service.py::TestImportExportServiceParseAndPreview -v` 输出 `3 passed`；`pytest tests/unit/test_import_export_service.py::TestImportExportServiceExecuteImport -v` 输出 `2 passed`；`pytest tests/unit/test_import_export_service.py::TestImportExportServiceCreateExport -v` 输出 `2 passed`。

---

### Step 10: Write and run verify script

在 `docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh` 创建：

```bash
#!/bin/bash
set -e
export PYTHONPATH=src

echo "=== ruff check ==="
ruff check src/services/import_export_service.py src/db/models/import_job.py src/db/models/export_job.py
echo "=== ruff format ==="
ruff format --check src/services/import_export_service.py src/db/models/import_job.py src/db/models/export_job.py
echo "=== python import check ==="
python -c "from db.models.import_job import ImportJob; from db.models.export_job import ExportJob; print('models ok')"
python -c "from services.import_export_service import ImportExportService; print('service ok')"
echo "=== pytest ==="
pytest tests/unit/test_import_export_service.py -v --tb=short
echo "=== ALL DONE ==="
```

运行：

```bash
bash docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh
```

**完成判定**：脚本输出 ruff0 errors + all tests passed。

---

## 6. 验收

- [ ] `python -c "from db.models.import_job import ImportJob; print(ImportJob.__tablename__)"` 输出 `import_jobs`
- [ ] `python -c "from db.models.export_job import ExportJob; print(ExportJob.__tablename__)"` 输出 `export_jobs`
- [ ] `ruff check src/services/import_export_service.py src/db/models/import_job.py src/db/models/export_job.py` 输出 `0 errors`
- [ ] `grep -n "async def validate_file" src/services/import_export_service.py` 输出行号（非空）
- [ ] `grep -n "async def parse_and_preview" src/services/import_export_service.py` 输出行号（非空）
- [ ] `grep -n "async def execute_import" src/services/import_export_service.py` 输出行号（非空）
- [ ] `grep -n "async def create_export" src/services/import_export_service.py` 输出行号（非空）
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceValidateFile -v` 输出 `5 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceParseAndPreview -v` 输出 `3 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceExecuteImport -v` 输出 `2 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceCreateExport -v` 输出 `2 passed`
- [ ] `bash docs/dev-plan/70-platform/verify/0676_test_import_export_core.sh` 全绿

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `execute_import` writes CustomerModel/OpportunityModel rows inside the same method, making it hard to unit-test without a real DB session | 中 | 中 | `execute_import` with `session=None` returns a mock `ImportJob` (id=0) — unit tests use this path; integration tests with a real session verify DB writes separately |
| `ImportJob`/`ExportJob` ORM models created here conflict with models delivered later by #675 (duplicate `import_jobs` table definition) | 中 | 高 | Coordinate with #675 before generating migration; if both boards define the same table, #675's migration wins and this board only adds service method stubs |
| File bytes decoded via UTF-8 then re-decoded in `parse_and_preview`, causing double-decode errors for non-UTF-8 content in GBK-encoded CSV | 低 | 中 | `FileHelper.read_csv` already handles encoding fallback; `validate_file` catches `UnicodeDecodeError` and raises `ValidationException`; GBK files that pass `read_csv` will be accepted |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/services/import_export_service.py src/db/models/import_job.py src/db/models/export_job.py src/db/models/__init__.py alembic/env.py tests/unit/test_import_export_service.py && git commit -m "feat(import-export): add validate_file, parse_and_preview, execute_import, create_export (issue #676)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块本行状态
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ 0676-Implement-ImportExportService-Core-Methods 完成 (W20.4)
# - PR/Commit: <link>
# -关键产物: ImportJob/ExportJob ORM models, validate_file(), parse_and_preview(), execute_import(), create_export()
# - 验收: pytest tests/unit/test_import_export_service.py -v 全 passed ✓
# - 下一步赋能: unit tests for new methods (0679), import history & error reporting (0678)

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- 上游 dependency board: [`0678-add-import-history-and-error-reporting`](../70-platform/0678-add-import-history-and-error-reporting.md) — uses `ImportJob` model from this board
- 父 issue: #34 — 总览 issue
- 项目内：`ImportExportService` 实现参考 [`src/services/import_export_service.py`](../../../src/services/import_export_service.py) L16-L423
- 项目内：`FileHelper` - 文件解析参考 [`src/utils/file_helper.py`](../../../src/utils/file_helper.py)
- 项目内：Error handling 规范 TBD - 待验证：错误异常类路径
- CLAUDE.md §「Service Pattern」：service returns ORM + raises AppException
- CLAUDE.md §「Unit Test SQL Mocks」：MockState / make_mock_session 使用规范

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
