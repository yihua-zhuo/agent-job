# 报表导出 · Signed URL PDF/Excel/CSV download

| 元数据 | 值 |
|---|---|
| Issue | #545 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | TBD - 待验证：0544-report-data-pipeline-signed-url 文件路径待确认 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Analytics reports currently return raw data but have no way to export that data as a persistent, downloadable file. Users need to archive reports in PDF for sharing with stakeholders who do not have access to the CRM, and to process report data in Excel or CSV for downstream analysis. Without a dedicated export pipeline, users resort to manual copy-paste, which is error-prone and does not scale.

### 1.2 做完后

- **用户视角**: A user POSTs report configuration (type, filters, columns) to `POST /analytics/reports/generate` and receives a signed URL valid for a limited time window. Clicking the URL triggers a file download with the correct `Content-Type` header (PDF/Excel/CSV). The signed URL expires after a configurable TTL, and the temporary file is deleted from storage.
- **开发者视角**: A new `ReportExportService` in `src/services/report_export.py` handles format selection, file generation, and URL signing. The `POST /analytics/reports/generate` endpoint delegates to this service. A `GET /analytics/reports/files/{token}` endpoint serves the stored file by validating the signed token and streaming the content with the appropriate MIME type.

### 1.3 不做什么（剔除）

- [ ] Long-term file storage / persistence to cloud object stores (S3, GCS) — temporary local storage only
- [ ] Authentication/authorization beyond tenant isolation — the signed URL itself is the access credential for the duration of the TTL
- [ ] Scheduled / recurring report generation — this endpoint is on-demand only
- [ ] Report template management (creating/editing templates)

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_report_export.py -v` → all pass
- [ ] `PYTHONPATH=src pytest tests/integration/test_report_export_integration.py -v` → all pass
- [ ] `ruff check src/services/report_export.py src/api/routers/analytics_reports.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- [ ] `POST /analytics/reports/generate` with valid payload returns `{"success": true, "data": {"url": "..."}}` with HTTP 200

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/analytics_reports.py` L? — 现有 analytics router，需确认当前 `/analytics/reports` 前缀下有哪些 endpoint

TBD - 待验证：`src/services/` L? — 是否有现有 report service 可参考；或 `src/services/` 下已有 analytics 相关 service

No existing `report_export.py` service — this is a greenfield module.

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/analytics_reports.py` — 新增 `/generate` POST endpoint 和 `/files/{token}` GET endpoint
- 要建：
  - `src/services/report_export.py` — ReportExportService：文件生成（PDF/Excel/CSV）、签名 URL 创建与验证、临时文件生命周期管理
  - `src/db/models/report_file.py` — ReportFile ORM model：存储临时文件的元信息（tenant_id, filename, format, expires_at, storage_path）
  - `alembic/versions/<id>_add_report_file_table.py` — 创建 `report_files` 表，含 `tenant_id` 索引
  - `tests/unit/test_report_export.py` — 单元测试（mock session + mock storage）
  - `tests/integration/test_report_export_integration.py` — 集成测试（真实 DB + 临时文件存储）

### 2.3 缺什么

- [ ] No service layer for multi-format report file generation (PDF/Excel/CSV)
- [ ] No signed URL mechanism for time-limited file access
- [ ] No `ReportFile` ORM model for tracking temporary file metadata
- [ ] No `POST /analytics/reports/generate` endpoint
- [ ] No `GET /analytics/reports/files/{token}` endpoint to serve files
- [ ] No temporary file cleanup job (TTL-based expiry)
- [ ] No migration for `report_files` table

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/report_export.py` | ReportExportService：生成 PDF/Excel/CSV 文件，创建和验证签名 URL，管理临时文件生命周期 |
| `src/db/models/report_file.py` | ReportFile ORM model：存储报告文件的元信息（tenant_id, filename, format, expires_at, storage_path） |
| `alembic/versions/<id>_add_report_file_table.py` | 创建 `report_files` 表，含 `tenant_id` 索引 |
| `tests/unit/test_report_export.py` | 单元测试：mock DB + mock storage，验证各格式文件生成和签名 URL 逻辑 |
| `tests/integration/test_report_export_integration.py` | 集成测试：真实 DB + 临时文件目录，验证端到端生成 + 下载流程 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/api/routers/analytics_reports.py` 文件路径 | 新增 `POST /analytics/reports/generate` 和 `GET /analytics/reports/files/{token}` 两个 endpoint |
| `alembic/env.py` | 将 `ReportFile` model 导入，确保 autogen 可见 |

### 3.3 新增能力

- **Service method**：`ReportExportService.generate(self, tenant_id: int, report_config: ReportConfig) -> str` — 生成文件并返回签名 URL（内部调用各格式生成器）
- **Service method**：`ReportExportService.validate_token(self, token: str) -> ReportFile | None` — 验证签名 token，返回文件元信息或 None
- **API endpoint**：`POST /analytics/reports/generate` → `{"success": true, "data": {"url": "/analytics/reports/files/{token}"}}`
- **API endpoint**：`GET /analytics/reports/files/{token}` → streams file with `Content-Type: application/pdf` / `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` / `text/csv`
- **ORM model**：`ReportFile` in `src/db/models/report_file.py`
- **Migration**：`alembic upgrade head` 创建 `report_files` 表（含 `tenant_id` 索引，`expires_at` 索引用于清理查询）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 reportlab 而非 weasyprint**：weasyprint requires GTK+ and Cairo system libraries which are complex to install in Docker and CI environments. reportlab is a pure-Python PDF library with no system-level dependencies, making it reliably reproducible across all environments.
- **选 HMAC-SHA256 token 而非 Redis 队列**：Storing signed URL state in Redis introduces an external dependency and operational overhead for a time-limited access pattern. A self-contained HMAC-SHA256 token encoding `{file_id}:{expires_at}:{signature}` is sufficient: the signature prevents tampering, `expires_at` enforces TTL, and no external state is required.
- **选本地临时文件存储而非云对象存储**：The requirement is temporary file storage with signed URL access. S3/GCS adds configuration complexity and external service dependency. Local filesystem under a configurable `REPORT_EXPORT_DIR` (default `/tmp/report_exports`) meets the requirement; cleanup is handled by a TTL-based job in the service.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `reportlab` | `>=4.0` | Pure-Python PDF generation, no system deps |
| `openpyxl` | `>=3.1` | Excel export, already in standard CRM stack |
| 内部 `csv` (stdlib) | built-in | No version constraint; used for CSV generation |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- `ReportFile` model 列名禁止使用 `metadata`（与 `Base.metadata` 冲突）→ 使用 `file_metadata` 或 `attrs`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- Router inject session via `session: AsyncSession = Depends(get_db)`，**不**用 `async with get_db()`
- Import 路径：`from db.models.report_file import ReportFile`，**不**用 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogen emits `sa.JSON()` instead of `sa.JSONB()`** → 规避：创建 migration 后手动将 `JSON()` 改为 `JSONB()`，并在 migration 注释中记录此项
2. **ReportLab `table.setStyle` crashes with empty row data** → 规避：在写入表格前过滤空行，`if not row or all(v is None for v in row): continue`
3. **Signed URL token leakage if `SECRET_KEY` rotates** → 规避：token TTL 设为 1 小时（`SIGNED_URL_TTL_SECONDS=3600`），旧密钥期间生成的 URL 在过期前自然失效；新密钥生成的文件无法用旧密钥访问（`validate_token` 会返回 None）
4. **Temporary file not deleted after TTL if service restarts** → 规避：`ReportExportService.__init__` 时启动一个异步清理协程，扫描 `expires_at < now` 的记录并删除对应文件；也可由 `POST /analytics/reports/generate` 在每次调用时触发一次批清理（限制每次最多删 100 条）

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ReportFile ORM model 和数据库迁移

在 `src/db/models/` 下创建 `report_file.py`，定义 `ReportFile` SQLAlchemy ORM model。表名 `report_files`，包含：`id`（自增主键）、`tenant_id`（索引）、`original_filename`（如 `"monthly-sales.pdf"`）、`format`（`pdf` / `excel` / `csv` 枚举）、`storage_path`（本地文件路径）、`expires_at`（UTC datetime，用于 TTL 清理）、`created_at`。

将 `ReportFile` 导入到 `alembic/env.py`（在 `from src.db.models import *` 之后或显式 import 行），然后生成 migration。

操作：
- a) 创建 `src/db/models/report_file.py`
- b) 更新 `alembic/env.py` 添加 `from src.db.models.report_file import ReportFile`
- c) 生成 migration：`alembic revision --autogenerate -m "add report_files table"`
- d) 手动修改生成的 migration：将 `sa.JSON()` 改为 `sa.JSONB()`（如有）；确认 `tenant_id` 有 `index=True`；确认 `expires_at` 有 `index=True`（用于清理查询）；填写 `downgrade()` 方法（删除表）

```python
# src/db/models/report_file.py
from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

class ReportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"

class ReportFile(Base):
    __tablename__ = "report_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf/excel/csv
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_report_files_tenant_expires", "tenant_id", "expires_at"),
    )
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 2: 实现 ReportExportService — 文件生成逻辑

在 `src/services/report_export.py` 中实现 `ReportExportService`：

**格式生成器**（内部私有方法）：
- `_generate_pdf(tenant_id: int, report_config: ReportConfig, dest_path: str)` — 使用 reportlab 的 `SimpleDocTemplate` + `Table`，写入 `dest_path`
- `_generate_excel(tenant_id: int, report_config: ReportConfig, dest_path: str)` — 使用 openpyxl 的 `Workbook`，写 `Sheet1`，输出 `dest_path`
- `_generate_csv(tenant_id: int, report_config: ReportConfig, dest_path: str)` — 使用 `csv.writer`，输出 `dest_path`

**签名逻辑**：
- `_create_signed_token(file_id: int, expires_at: datetime) -> str` — HMAC-SHA256(secret, f"{file_id}:{expires_at_ts}")，返回 `base64url(file_id:expires_at:signature)`
- `validate_token(token: str) -> ReportFile | None` — 解码 token，验证 HMAC 签名，确认未过期，返回 `ReportFile` 或 `None`

**清理逻辑**：
- `_cleanup_expired()` — 查询 `expires_at < utcnow()` 的 `ReportFile`，删除对应 `storage_path` 文件和 DB 记录（限制每次 100 条）

操作：
- a) 创建 `src/services/report_export.py`
- b) 实现 `ReportExportService.__init__(self, session: AsyncSession)` — 存储 session，读取 `REPORT_EXPORT_DIR` 环境变量（默认 `/tmp/report_exports`），确保目录存在
- c) 实现三个格式生成私有方法
- d) 实现签名/验证方法
- e) 实现清理协程

```python
# src/services/report_export.py（关键片段）
import csv
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone, timedelta
from base64 import urlsafe_b64encode, urlsafe_b64decode

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.report_file import ReportFile
from pkg.errors.app_exceptions import NotFoundException

REPORT_EXPORT_DIR = os.environ.get("REPORT_EXPORT_DIR", "/tmp/report_exports")
SIGNED_URL_SECRET = os.environ.get("SIGNED_URL_SECRET", secrets.token_hex(32))
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", "3600"))

class ReportExportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        os.makedirs(REPORT_EXPORT_DIR, exist_ok=True)

    async def generate(self, tenant_id: int, report_config: ReportConfig) -> str:
        file_id = secrets.token_hex(8)
        dest_path = os.path.join(REPORT_EXPORT_DIR, f"{file_id}.{report_config.format}")
        if report_config.format == "pdf":
            self._generate_pdf(tenant_id, report_config, dest_path)
        elif report_config.format == "excel":
            self._generate_excel(tenant_id, report_config, dest_path)
        elif report_config.format == "csv":
            self._generate_csv(tenant_id, report_config, dest_path)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=SIGNED_URL_TTL_SECONDS)
        report_file = ReportFile(
            tenant_id=tenant_id,
            original_filename=report_config.filename,
            format=report_config.format,
            storage_path=dest_path,
            expires_at=expires_at,
        )
        self.session.add(report_file)
        await self.session.commit()
        await self._cleanup_expired()
        return self._create_signed_token(report_file.id, expires_at)

    def validate_token(self, token: str) -> ReportFile | None:
        try:
            raw = urlsafe_b64decode(token)
            file_id_str, expires_ts_str, sig_b64 = raw.split(b":")
            file_id = int(file_id_str)
            expires_at = datetime.fromtimestamp(int(expires_ts_str), tz=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return None
            expected = hmac.new(
                SIGNED_URL_SECRET.encode(),
                f"{file_id}:{int(expires_at.timestamp())}".encode(),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(sig_b64, expected):
                return None
            return file_id  # caller resolves to ReportFile via session
        except Exception:
            return None

    async def _cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        stmt = select(ReportFile).where(ReportFile.expires_at < now).limit(100)
        result = await self.session.execute(stmt)
        expired = result.scalars().all()
        for f in expired:
            if os.path.exists(f.storage_path):
                os.remove(f.storage_path)
            await self.session.delete(f)
        if expired:
            await self.session.commit()
```

**完成判定**：`ruff check src/services/report_export.py` → 0 errors

---

### Step 3: 实现 POST /analytics/reports/generate endpoint

在 `src/api/routers/analytics_reports.py` 中添加 `POST /analytics/reports/generate`：

**Request body**（`ReportGenerateRequest` Pydantic model）：
```python
class ReportGenerateRequest(BaseModel):
    format: Literal["pdf", "excel", "csv"]  # required
    filename: str = Field(default="report", max_length=255)  # without extension
    columns: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    data: list[dict[str, Any]]  # report rows — caller provides the data to export
```

**Response**（`ReportGenerateResponse`）：
```python
class ReportGenerateResponse(BaseModel):
    url: str  # "/analytics/reports/files/{token}"
    filename: str  # "report.pdf"
    format: str
    expires_in_seconds: int  # SIGNED_URL_TTL_SECONDS
```

Endpoint 调用 `ReportExportService.generate(tenant_id, report_config)`，将返回的签名 token 拼接为相对 URL。

操作：
- a) 定义 `ReportGenerateRequest` 和 `ReportGenerateResponse` Pydantic model
- b) 添加 `POST /analytics/reports/generate` endpoint
- c) 注入 `ReportExportService(session)`，调用 `generate`

```python
# src/api/routers/analytics_reports.py（新增 endpoint）
@router.post("/reports/generate", response_model=ReportGenerateResponse)
async def generate_report(
    req: ReportGenerateRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    report_config = ReportConfig(
        format=req.format,
        filename=req.filename,
        columns=req.columns,
        filters=req.filters,
        data=req.data,
    )
    svc = ReportExportService(session)
    token = await svc.generate(ctx.tenant_id, report_config)
    return {
        "success": True,
        "data": {
            "url": f"/analytics/reports/files/{token}",
            "filename": f"{req.filename}.{req.format}",
            "format": req.format,
            "expires_in_seconds": int(os.environ.get("SIGNED_URL_TTL_SECONDS", "3600")),
        },
    }
```

**完成判定**：`ruff check src/api/routers/analytics_reports.py` → 0 errors

---

### Step 4: 实现 GET /analytics/reports/files/{token} endpoint

添加 `GET /analytics/reports/files/{token}` endpoint：

1. 调用 `ReportExportService.validate_token(token)` — 返回 `file_id` 或 `None`
2. 若 `None`：抛出 `NotFoundException("Report file")`（或 `404`）
3. 用 `file_id` 从 session 查询 `ReportFile`
4. 读取 `storage_path` 文件内容，构造 `StreamingResponse`
5. 根据 `format` 设置正确的 `Content-Type`：
   - `pdf` → `application/pdf`
   - `excel` → `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
   - `csv` → `text/csv; charset=utf-8`
6. `Content-Disposition: attachment; filename="{original_filename}"`

**注意**：此 endpoint 不需要 `require_auth`（token 本身就是访问凭证），但可选择性地仍然验证 `tenant_id`（从 DB 记录中读取，与请求来源无关）。

操作：
- a) 在 `analytics_reports.py` 中添加 `GET /analytics/reports/files/{token}` endpoint
- b) 使用 `StreamingResponse` 避免将大文件读入内存

```python
# src/api/routers/analytics_reports.py（新增 endpoint）
from fastapi.responses import StreamingResponse

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}

@router.get("/reports/files/{token}")
async def serve_report_file(
    token: str,
    session: AsyncSession = Depends(get_db),
):
    svc = ReportExportService(session)
    file_id = svc.validate_token(token)
    if file_id is None:
        raise NotFoundException("Report file")
    result = await session.execute(
        select(ReportFile).where(ReportFile.id == file_id)
    )
    report_file = result.scalar_one_or_none()
    if report_file is None or not os.path.exists(report_file.storage_path):
        raise NotFoundException("Report file")
    content_type = CONTENT_TYPES.get(report_file.format, "application/octet-stream")
    return StreamingResponse(
        iter(lambda: open(report_file.storage_path, "rb").read(), b""),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{report_file.original_filename}"'},
    )
```

**完成判定**：`ruff check src/api/routers/analytics_reports.py` → 0 errors

---

### Step 5: 编写单元测试

在 `tests/unit/test_report_export.py` 中编写测试：

**Mock fixtures**：
- `mock_db_session` — 使用 `make_mock_session` 配置 `report_file_handler`（若 conftest.py 无此 handler，按 CLAUDE.md 添加一个新的）
- `mock_storage` — fixture 用 `tempfile.TemporaryDirectory()` mock `REPORT_EXPORT_DIR`

**测试用例**：
- `test_generate_pdf_creates_file_and_db_record` — 调用 `generate`，验证文件存在、DB 记录存在、返回 token
- `test_generate_excel_creates_valid_xlsx` — 调用 `generate(format="excel")`，验证文件可被 openpyxl 打开
- `test_generate_csv_creates_valid_csv` — 调用 `generate(format="csv")`，读取文件验证内容
- `test_validate_token_returns_file_id_on_valid_token` — 生成 token，验证 `validate_token` 返回 file_id
- `test_validate_token_returns_none_on_expired_token` — 修改系统时间测试过期（mock datetime）
- `test_validate_token_returns_none_on_tampered_token` — 篡改 token 尾部落返回 None
- `test_cleanup_expired_deletes_old_files` — 插入过期的 ReportFile，调用清理，验证文件和 DB 记录均被删除

操作：
- a) 如需要，在 `tests/unit/conftest.py` 添加 `make_report_file_handler(state)` 工厂函数
- b) 创建 `tests/unit/test_report_export.py`
- c) 实现上述测试用例

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_report_export.py -v` → all passed

---

### Step 6: 编写集成测试

在 `tests/integration/test_report_export_integration.py` 中编写测试：

使用 `db_schema` fixture（自动创建/删除所有表），`tenant_id` fixture，`async_session`。

**测试用例**：
- `test_generate_and_download_pdf_round_trip` — POST `/analytics/reports/generate`，获取 token，GET `/analytics/reports/files/{token}`，验证 `Content-Type` 和文件内容
- `test_generate_and_download_excel_round_trip` — 同上，format=excel，验证 `Content-Disposition` 包含 `.xlsx`
- `test_generate_and_download_csv_round_trip` — 同上，format=csv
- `test_generate_with_empty_data` — 验证空数据集导出成功（PDF 有表头，Excel 有表头行，CSV 有 header 行）
- `test_expired_token_returns_404` — 手动将 `expires_at` 设为过去时间，再访问 signed URL，验证 404

操作：
- a) 创建 `tests/integration/test_report_export_integration.py`
- b) 实现上述测试用例

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_report_export_integration.py -v` → all passed

---

### Step 7: 最终 lint + migration 验证

运行完整检查：

操作：
- a) `ruff check src/services/report_export.py src/api/routers/analytics_reports.py src/db/models/report_file.py` → 0 errors
- b) `ruff format --check src/services/report_export.py src/api/routers/analytics_reports.py src/db/models/report_file.py` → 0 non-formatted
- c) `PYTHONPATH=src mypy src/services/report_export.py src/api/routers/analytics_reports.py` → 0 errors（可选，如有 mypy 配置）
- d) `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

**完成判定**：以上 4 条全部通过

---

## 6. 验收

- [ ] `ruff check src/services/report_export.py src/api/routers/analytics_reports.py src/db/models/report_file.py` → 0 errors
- [ ] `ruff format --check src/services/report_export.py src/api/routers/analytics_reports.py src/db/models/report_file.py` → 0 non-formatted
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_export.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_report_export_integration.py -v` → all passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- [ ] 端到端：启动服务后，`POST /analytics/reports/generate` with `{"format":"csv","filename":"test","data":[{"col1":"val1"}]}` 返回 `{"success":true,"data":{"url":"/analytics/reports/files/..."}}`；用返回的 URL `GET /analytics/reports/files/...` 返回 `Content-Type: text/csv; charset=utf-8` 和 CSV 内容

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 大文件 PDF/Excel 生成导致服务内存峰值 | 中 | 中 | 在 `_generate_pdf` / `_generate_excel` 中对行数超过 10000 的数据分批写入；PDF 使用 `SimpleDocTemplate` 的 `pagebreak`；Excel 限制 sheet 最多 1048576 行（Excel max） |
| 本地临时文件存储磁盘占满 | 低 | 高 | 配置 `REPORT_EXPORT_DIR` 到独立分区；清理协程在每次 `generate` 调用时运行；可添加定时 cron job 独立清理 |
| HMAC secret 泄露导致签名伪造 | 低 | 高 | `SIGNED_URL_SECRET` 必须从环境变量读取，不硬编码；泄露后立即轮换（已签URL失效，但数据安全） |
| reportlab / openpyxl 依赖版本不兼容现有环境 | 低 | 中 | 在 `pyproject.toml` 中固定版本（`reportlab>=4.0,<5.0`，`openpyxl>=3.1,<4.0`）；CI 在 `pip install` 后运行 `python -c "import reportlab; import openpyxl"` 验证导入 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/report_export.py src/db/models/report_file.py src/api/routers/analytics_reports.py alembic/ tests/unit/test_report_export.py tests/integration/test_report_export_integration.py
git commit -m "feat(analytics): add report export PDF/Excel/CSV with signed URL download"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): report export with signed URL download (closes #545)" --body "## Summary\n- POST /analytics/reports/generate returns signed URL for PDF/Excel/CSV download\n- GET /analytics/reports/files/{token} serves file with correct Content-Type\n- ReportExportService handles format generation, signing, and TTL cleanup\n- ReportFile ORM model tracks temporary file metadata\n\n## Test plan\n- [ ] pytest tests/unit/test_report_export.py -v\n- [ ] pytest tests/integration/test_report_export_integration.py -v\n- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/` 下是否存在类似的文件生成 service（如票据导出、合同 PDF 生成），其格式选择和存储模式可参考
- 父 issue：#56（Analytics 模块总览）
- 依赖：#544（Report data pipeline signed URL）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
