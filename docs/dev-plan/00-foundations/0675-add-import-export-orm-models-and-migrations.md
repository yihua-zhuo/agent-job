# 0675 · Define ImportJob and ExportJob ORM models and migration

| 元数据 | 值 |
|---|---|
| 周次 | W21.1 |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：下游服务 board 路径（0676-implement-import-export-service-core-methods.md 尚不存在） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The Import/Export subsystem (platform category, `70-platform`) requires persistent storage for import and export job metadata. Currently no ORM models or database tables exist for `ImportJob` or `ExportJob`. Downstream board #676 (`ImportExportService`) needs to read/write job state (status, progress, errors) from the database, but the underlying tables have not been created yet. This board defines the two ORM models and generates the Alembic migration — the prerequisite for all downstream import/export work on this feature track.

### 1.2 做完后

- **用户视角**：No direct user change — this is pure infrastructure.
- **开发者视角**：`alembic upgrade head` creates `import_jobs` and `export_jobs` tables. Both models can be imported from `src.db.models` and used in services and routers built by downstream boards. `to_dict()` serialization is defined on both models.

### 1.3 不做什么（剔除）

- [ ] No service layer — #676 owns `ImportExportService`.
- [ ] No REST API — router belongs to a future import/export router board.
- [ ] No file processing logic — file read/write stays in `FileHelper` or service layer.
- [ ] No unit tests for the model layer — model unit tests belong to a dedicated test board if needed; this board stops at migration.

### 1.4 关键 KPI

- `alembic upgrade head` → `import_jobs` and `export_jobs` tables present in `alembic_dev`.
- `alembic downgrade -1` → both tables dropped cleanly.
- `ruff check src/db/models/import_job.py src/db/models/export_job.py` → zero warnings/errors.
- `mypy src/db/models/import_job.py src/db/models/export_job.py` → zero errors.

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块. No `import_job` or `export_job` model files exist yet in `src/db/models/`. The `alembic/env.py` imports all models via `import db.models` (line 14), so any new model file in `src/db/models/` will be automatically picked up by the migration system once it is importable.

主入口：[`src/db/models/customer.py`](../../../src/db/models/customer.py) L1-L57 — 参考 ORM 模型风格

```startLine:11:endLine:33:src/db/models/customer.py
class CustomerModel(Base):
    """Customer entity mapped to the `customers` table."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="lead", nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recycle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recycle_history: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../../alembic/env.py) - 确保 `import db.models` 能 pick up 新模型文件；已有点头14的 `import db.models` 无需修改
- 要建：
  - `src/db/models/import_job.py` - `ImportJobModel` ORM 模型（id, tenant_id, entity_type, file_path, status, total_rows, processed_rows, error_rows, created_at）
  - `src/db/models/export_job.py` - `ExportJobModel` ORM 模型（id, tenant_id, entity_type, fields JSON, filters JSON, file_path, status, expires_at）
  - `alembic/versions/<id>_create_import_jobs_and_export_jobs_tables.py` - Alembic 迁移脚本

### 2.3 缺什么

- [ ] No `ImportJobModel` ORM model file.
- [ ] No `ExportJobModel` ORM model file.
- [ ] No Alembic migration for `import_jobs` and `export_jobs` tables.
- [ ] `alembic/env.py` already has `import db.models` on line 14 — model files will be picked up automatically, no env.py change needed.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `src/db/models/import_job.py` | `ImportJobModel` ORM model: id, tenant_id, entity_type, file_path, status, total_rows, processed_rows, error_rows, created_at |
| `src/db/models/export_job.py` | `ExportJobModel` ORM model: id, tenant_id, entity_type, fields, filters, file_path, status, expires_at |
| `alembic/versions/<id>_create_import_jobs_and_export_jobs_tables.py` | Alembic migration creating both tables with all columns, indexes |
| `docs/dev-plan/70-platform/0675_verify.sh` | Acceptance script: ruff + mypy + alembic upgrade/downgrade cycle |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../../alembic/env.py) | 无需修改 — `import db.models` on line 14 已覆盖新模型文件 |

### 3.3 新增能力

- **Migration**: `alembic upgrade head` → `import_jobs` + `export_jobs` tables exist.
- **verify 脚本**: `bash docs/dev-plan/70-platform/0675_verify.sh`
- **Model imports**: `from src.db.models.import_job import ImportJobModel` and `from src.db.models.export_job import ExportJobModel` available for downstream boards.

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `server_default=func.now()` 而非 Python-side `datetime.now(UTC)`**：Migration-defined server defaults are evaluated at INSERT time on the DB side, which is more reliable than Python-side defaults that can be wrong if the app process clock drifts.
- **选 `String(length=255)` for `file_path`**：Stores absolute or relative file system path; 255 characters is sufficient for all typical path use cases (no PostgreSQL path type needed).
- **选 `JSON` (not `JSONB`) for `fields` and `filters`**：Fields and filters are configuration data written once at job creation and rarely queried by individual key. JSON is sufficient; upgrade to JSONB only if GIN index queries become necessary.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `alembic` | from `pyproject.toml` | Already pinned in project |
| `sqlalchemy` | `2.x` | Already pinned in project; required for async `Mapped` column syntax |

### 4.3 兼容性约束

- Migration must be reversible (`downgrade()` drops both tables; `export_jobs` must be dropped before `import_jobs` due to no FK but ordered for clarity).
- Migration must use `Revises:` pointing to the current head revision (run `alembic current` to confirm).
- Status field values (pending/running/done/failed for import; similar for export) are stored as plain strings — no enum type is used, matching the pattern in `TicketModel` and `CustomerModel`.

### 4.4 已知坑

1. **Autogenerate may emit `default=None` instead of `server_default=sa.text('now()')` for timestamp columns** → 规避：review the generated migration and manually change any `nullable=True, default=None` on `created_at`/`updated_at` to `server_default=sa.text('now()'), nullable=False`. Run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` to confirm the cycle is clean.
2. **JSON column defaults in autogenerate** → 规避：if autogenerate emits `default={}` for `fields` or `filters`, change to `server_default=sa.text("'{}'::jsonb")` or leave as Python-side `default=dict` and let SQLAlchemy handle it. Verify by checking the migration file before applying.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/db/models/import_job.py`

创建 `ImportJobModel` ORM 模型，字段定义与 issue 规格一致：

```python
# src/db/models/import_job.py
"""ImportJob ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ImportJobModel(Base):
    """Stores import job metadata and progress."""

    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "entity_type": self.entity_type,
            "file_path": self.file_path,
            "status": self.status,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "error_rows": self.error_rows,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/import_job.py` → 0 errors.

---

### Step 2: Create `src/db/models/export_job.py`

创建 `ExportJobModel` ORM 模型，字段定义与 issue 规格一致：

```python
# src/db/models/export_job.py
"""ExportJob ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ExportJobModel(Base):
    """Stores export job configuration and progress."""

    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "entity_type": self.entity_type,
            "fields": self.fields or {},
            "filters": self.filters or {},
            "file_path": self.file_path,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/export_job.py` → 0 errors.

---

### Step 3: Bring up alembic_dev database and run existing migrations to head

操作：
- a) 确保 `alembic_dev` 数据库干净且在当前 migration head：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
```

- b) 导出 env 并运行现有迁移到 head：

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

**完成判定**：`alembic current` → 显示当前 head revision（例如 `c94d682d4b03`）。

---

### Step 4: Generate autogenerate migration for import_jobs and export_jobs

操作：
- a) 运行 alembic autogenerate：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic revision --autogenerate -m "create import_jobs and export_jobs tables"
```

- b) 打开生成的 migration 文件（`alembic/versions/<id>_create_import_jobs_and_export_jobs_tables.py`），验证 `op.create_table` 调用包含所有列：

**ImportJobModel 列**：
- id (Integer, PK), tenant_id (Integer, indexed), entity_type (String(100)), file_path (String(255)), status (String(50), default="pending"), total_rows (Integer, default=0), processed_rows (Integer, default=0), error_rows (Integer, default=0), created_at (DateTime, server_default=now())

**ExportJobModel 列**：
- id (Integer, PK), tenant_id (Integer, indexed), entity_type (String(100)), fields (JSON), filters (JSON), file_path (String(255), nullable), status (String(50), default="pending"), expires_at (DateTime, nullable), created_at (DateTime, server_default=now())

- c) 修正 autogenerate 错误的地方（String 长度、Boolean 默认语法、timestamp server_default 等）。

示例代码（expected migration structure）：

```python
# alembic/versions/<id>_create_import_jobs_and_export_jobs_tables.py
def upgrade() -> None:
    op.create_table('import_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('total_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('processed_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_jobs_tenant_id'), 'import_jobs', ['tenant_id'])

    op.create_table('export_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('fields', sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column('filters', sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column('file_path', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_jobs_tenant_id'), 'export_jobs', ['tenant_id'])
```

**完成判定**：`ls alembic/versions/*import*jobs*.py` 返回新的 migration 文件。

---

### Step 5: Apply migration and verify upgrade/downgrade cycle

操作：
- a) Apply upgrade：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

- b) 确认两个表都存在：

```bash
docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt import_jobs"
docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt export_jobs"
docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d import_jobs"
docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d export_jobs"
```

- c) 运行 downgrade 再 upgrade（clean cycle）：

```bash
alembic downgrade -1
alembic upgrade head
```

**完成判定**：`alembic downgrade -1` 以 exit code 0 退出，无错误。第二次 `alembic upgrade head` 以 exit code 0 退出，两个表都存在。

---

### Step 6: Create `docs/dev-plan/70-platform/0675_verify.sh`

操作：
- a) 创建验收脚本：

```bash
#!/usr/bin/env bash
set -e
export PYTHONPATH=src

echo "=== ruff check import_job ==="
ruff check src/db/models/import_job.py

echo "=== ruff check export_job ==="
ruff check src/db/models/export_job.py

echo "=== mypy import_job ==="
mypy src/db/models/import_job.py

echo "=== mypy export_job ==="
mypy src/db/models/export_job.py

echo "ALL CHECKS PASSED"
```

- b) `chmod +x docs/dev-plan/70-platform/0675_verify.sh`
- c) 本地运行确认 `ALL CHECKS PASSED`

**完成判定**：`bash docs/dev-plan/70-platform/0675_verify.sh` 以 exit code 0 退出，`ALL CHECKS PASSED` 为最后一行。

---

## 6. 验收

- [ ] `ruff check src/db/models/import_job.py` → 0 errors
- [ ] `ruff check src/db/models/export_job.py` → 0 errors
- [ ] `mypy src/db/models/import_job.py` → 0 errors
- [ ] `mypy src/db/models/export_job.py` → 0 errors
- [ ] `docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt"` shows both `import_jobs` and `export_jobs` after `alembic upgrade head`
- [ ] `bash docs/dev-plan/70-platform/0675_verify.sh` → `ALL CHECKS PASSED`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces wrong column types for JSON (uses `JSON` not `JSONB`, or emits `default=None`) | 中 | 中 | Manually fix the migration file: ensure `fields`/`filters` columns use `sa.JSON()` with `server_default=sa.text("'{}'::json")`; `created_at` must use `server_default=sa.text('now()')`, not Python-side default |
| Downgrade drops tables in wrong order | 低 | 高 | Edit migration file: ensure `op.drop_table('export_jobs')` appears before `op.drop_table('import_jobs')`; test downgrade cycle |
| Duplicate migration revision from parallel work | 低 | 低 | Use timestamp-based revision ID; if conflict, rename to include `_create_import_jobs_and_export_jobs` suffix |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/db/models/import_job.py src/db/models/export_job.py alembic/versions/*import*jobs*.py docs/dev-plan/70-platform/0675_verify.sh
git commit -m "feat(import-export): add ImportJob and ExportJob ORM models and migration (issue #675)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块本行状态
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0675] ORM models + migration 完成 (W21.1)
# - PR/Commit: <link>
# - 关键产物: src/db/models/import_job.py, src/db/models/export_job.py, alembic/versions/<id>_create_import_jobs_and_export_jobs_tables.py
# - 验收: bash docs/dev-plan/70-platform/0675_verify.sh 全绿 ✓
# - 下一步赋能: #676 (ImportExportService core methods)

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- ORM model reference（style）：[`src/db/models/customer.py`](../../../src/db/models/customer.py) L1-L57
- Alembic env：[`alembic/env.py`](../../../alembic/env.py) L14
- Example migration：TBD - 待验证：migrations 目录结构（c94d682d4b03 迁移文件路径待确认）
- Downstream board (service)：TBD - 待验证：下游服务 board 路径（0676-implement-import-export-service-core-methods.md 尚不存在）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
