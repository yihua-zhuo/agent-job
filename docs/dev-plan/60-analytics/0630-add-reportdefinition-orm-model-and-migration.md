# 报表定义 ORM 模型与数据库迁移 · 为分析模块建立 ReportDefinition 模型

| 元数据 | 值 |
|---|---|
| Issue | #630 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 报表功能（Router + Service 层依赖此 ORM） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #630 is a prerequisite for the analytics/reporting stack (subtask of #40). Currently the CRM has no `ReportDefinition` ORM model, so no persistence layer exists for storing report configurations. Every report-related feature (save, load, list, favourite) is blocked on this model.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动。
- **开发者视角**：
  - `ReportDefinition` ORM model available in `src/db/models/report.py`
  - Service and router layers can import it via `from db.models.report import ReportDefinition`
  - Alembic migration creates the `report_definitions` table with proper indexes

### 1.3 不做什么（剔除）

- [ ] Service layer (`src/services/`) — will be implemented in a downstream issue
- [ ] API router (`src/api/routers/`) — will be implemented in a downstream issue
- [ ] Unit tests beyond the model fixture — covered by downstream integration tests
- [ ] Seeding / fixture scripts for initial data

### 1.4 关键 KPI

- `alembic upgrade head` exits 0 and creates `report_definitions` table with all columns
- `alembic downgrade -1` exits 0 and drops the table
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` triple-run exits 0
- `ruff check src/db/models/report.py` → 0 errors
- `ruff check alembic/env.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models.report import ReportDefinition; print(ReportDefinition.__tablename__)"` → `report_definitions`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

No existing `src/db/models/report.py`. The ORM model does not yet exist. This is a greenfield addition.

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../alembic/env.py) — 添加 `from db.models.report import ReportDefinition` 导入
- 要建：
  - `src/db/models/report.py` — `ReportDefinition` ORM model
  - `alembic/versions/<id>_add_report_definitions_table.py` — Alembic migration
  - `tests/unit/test_report_model.py` — Model unit tests (optional, encouraged)

### 2.3 缺什么

- [ ] `src/db/models/report.py` — no `ReportDefinition` model exists; all downstream service/router work is blocked
- [ ] Alembic migration — no migration creates `report_definitions` table
- [ ] `alembic/env.py` — `ReportDefinition` not imported; `--autogenerate` will miss it if added later
- [ ] Column `config` type: must be `JSONB` (not plain `JSON`) to support PostgreSQL GIN index for JSON-path queries used by analytics features

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/report.py` | `ReportDefinition` SQLAlchemy ORM model |
| `alembic/versions/<id>_add_report_definitions_table.py` | Alembic migration creating `report_definitions` table |
| `tests/unit/test_report_model.py` | Unit tests for `ReportDefinition` model |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../alembic/env.py) | Add `from db.models.report import ReportDefinition` to import list so autogenerate sees it |

### 3.3 新增能力

- **ORM model**：`ReportDefinition` in `src/db/models/report.py`
  - Columns: `id` (PK), `tenant_id` (indexed), `name` (string), `report_type` (string/enum), `config` (JSONB), `owner_tenant_id`, `created_by`, `is_favorite` (bool, default False), `created_at` (utcnow), `updated_at` (utcnow onupdate)
- **Migration**：`alembic upgrade head` creates `report_definitions` table with `tenant_id` index
- **Model import in env**：`alembic/env.py` imports `ReportDefinition` so future `--autogenerate` picks it up

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSONB vs JSON**：Use `JSONB` column type. JSONB stores a binary parsed representation, enabling GIN index support and faster key-path queries — critical for the analytics config querying that will be added in downstream issues.
- **Separate file `report.py` vs. adding to existing model file**：New file per CLAUDE.md convention (one file per domain model). `report.py` is a standalone domain model analogous to `customer.py`, `user.py`, etc.
- **`owner_tenant_id` column**: Explicitly stored to support cross-tenant sharing scenarios in future analytics features. Not a foreign key constraint (no FK to avoid coupling), but always used with `tenant_id` filter in queries.

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：every SQL must `WHERE tenant_id = :tenant_id` — `ReportDefinition` includes `tenant_id` column with index
- Table name: `report_definitions` (plural snake_case, consistent with existing `customers`, `users` tables)
- `config` column: use `JSONB` with server default `{}` — NOT nullable, defaults to empty dict
- `is_favorite`: `Boolean` default `False`
- Timestamps: `created_at` = `server_default=func.now()`, `updated_at` = `onupdate=func.now()`
- Mixin pattern: inherit from `Base` (declarative) from `db.base` — same as all other models in this repo

### 4.4 已知坑

1. **SQLAlchemy model column named `metadata`** → Conflict with `Base.metadata`. The column must NOT be named `metadata`. Use `report_metadata` or `config` instead. This board uses `config` (JSONB) so no conflict.
2. **Alembic autogenerate writes `JSON` instead of `JSONB`** → After autogenerate, manually edit the migration file: replace `Column(JSON)` with `Column(JSONB)` and add `postgresql_using='using'` if GIN index is needed later.
3. **Alembic env.py must import every model** → If `ReportDefinition` is not imported in `alembic/env.py`, autogenerate will silently skip it. This board explicitly includes the import step.

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/report.py` ORM 模型

创建一个包含所有必需列的 `ReportDefinition` 模型。参考同仓 `src/db/models/customer.py` 的列定义模式。

操作：
a) 创建文件 `src/db/models/report.py`
b) 写入以下内容：

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ReportDefinition(Base):
    __tablename__ = "report_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    owner_tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)

    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_report_definitions_tenant_id", "tenant_id"),
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.report import ReportDefinition; print(ReportDefinition.__tablename__)"` → `report_definitions`

---

### Step 2: 更新 `alembic/env.py` 导入

在 `alembic/env.py` 的 model import 区块添加 `ReportDefinition` 导入。

操作：
a) 读取 `alembic/env.py`
b) 找到其他 model 导入的位置（如 `from db.models.customer import Customer`）
c) 在同一区域添加 `from db.models.report import ReportDefinition`

示例差异：

```diff
 from db.models.user import User
 from db.models.customer import Customer
+from db.models.report import ReportDefinition
 from db.models.pipeline import Pipeline
```

**完成判定**：`ruff check alembic/env.py` → 0 errors

---

### Step 3: 生成 Alembic migration

使用 `alembic revision --autogenerate` 生成迁移文件。

操作：
a) 确保 `DATABASE_URL` 指向干净的 `alembic_dev` 数据库（见 CLAUDE.md §Alembic Migrations）：
   ```bash
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head
   ```
b) 运行 autogenerate：
   ```bash
   alembic revision --autogenerate -m "add report_definitions table"
   ```
c) 编辑生成的迁移文件：确保 `config` 列使用 `JSONB` 而非 `JSON`，检查时间戳列的 `server_default` 是否正确

示例生成的 migration 关键段：

```python
def upgrade() -> None:
    op.create_table(
        "report_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=100), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_definitions_tenant_id", "report_definitions", ["tenant_id"], unique=False)
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 4: 验证 model 可被 SQLAlchemy 加载

验证 `ReportDefinition` model 可以被正确加载，无 import 错误。

操作：
```bash
PYTHONPATH=src python -c "
from db.base import Base
from db.models.report import ReportDefinition
from db.models import customer, user, pipeline
from sqlalchemy import inspect
mapper = inspect(ReportDefinition)
cols = [c.name for c in mapper.columns]
print('Columns:', cols)
assert 'tenant_id' in cols
assert 'config' in cols
assert 'is_favorite' in cols
print('OK')
"
```

**完成判定**：输出 `Columns: ['id', 'tenant_id', 'name', 'report_type', 'config', 'owner_tenant_id', 'created_by', 'is_favorite', 'created_at', 'updated_at']` 和 `OK`

---

### Step 5: Lint 最终产物

对所有变更文件运行 ruff 检查。

操作：
```bash
ruff check src/db/models/report.py
ruff check alembic/env.py
ruff format --check src/db/models/report.py
```

**完成判定**：所有命令 exit 0，无输出错误

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models.report import ReportDefinition; print(ReportDefinition.__tablename__)""` → `report_definitions`
- [ ] `ruff check src/db/models/report.py` → 0 errors
- [ ] `ruff check alembic/env.py` → 0 errors
- [ ] `ruff format --check src/db/models/report.py` → 0 errors
- [ ] `alembic upgrade head` → exit 0
- [ ] `alembic downgrade -1` → exit 0
- [ ] `alembic upgrade head` → exit 0
- [ ] `alembic history --verbose | head -20` → 新迁移出现在 history 中

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Migration 文件中 `config` 列被 autogenerate 写成 `JSON` 而非 `JSONB` | 中 | 中 — 未来 JSON 索引查询会无法创建 | 在迁移文件中手动替换 `JSON()` 为 `JSONB()`；手动添加 GIN 索引 |
| `alembic/env.py` 未正确导入导致 --autogenerate 漏掉 model | 中 | 高 — model 变更不会被检测 | 重新运行 Step 2 并确认 import 语句存在于 env.py |
| PostgreSQL 版本不支持 `JSONB` 的 GIN 索引（低版本特有） | 低 | 低 — 索引只是优化，不影响表创建 | 降级方案：在迁移中去掉 USING 子句，仅保留 B-tree 索引 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/report.py alembic/env.py alembic/versions/
git commit -m "feat(models): add ReportDefinition ORM model and migration

Closes #630"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(models): add ReportDefinition ORM model and migration" --body "Closes #630

## Summary
- Add `ReportDefinition` ORM model in `src/db/models/report.py`
- Register model in `alembic/env.py` imports
- Generate Alembic migration for `report_definitions` table

## Test plan
- [ ] `ruff check src/db/models/report.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0
- [ ] `PYTHONPATH=src python -c \"from db.models.report import ReportDefinition\"` → OK"

# 2. 更新进度
# - 在 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/customer.py`](../../src/db/models/customer.py) — 相同的 ORM 模式（列定义、索引、server_default）
- 父 issue：#40
- 相关 issue：#630（本文档）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
