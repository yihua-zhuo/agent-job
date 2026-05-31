# CustomerEnrichment · Add CustomerEnrichment ORM model and alembic migration

| 元数据 | 值 |
|---|---|
| Issue | #753 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0754: Implement EnrichmentAnalyticsService](0754-implement-enrichmentanalyticsservice.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The analytics pipeline (issue #513) requires a persisted table to store enrichment results per customer, keyed by tenant. No such table exists today — enrichment data is either recomputed on-the-fly or stored in a non-queryable format. Without a durable `CustomerEnrichment` table, downstream analytics endpoints have no reliable data source.

### 1.2 做完后

- **用户视角**：No direct user-visible change — this is a pure schema/backend addition.
- **开发者视角**：`CustomerEnrichment` ORM model is available in `src/db/models/enrichment.py`. Any service in this CRM can query enrichment records via SQLAlchemy with full tenant isolation. Alembic can generate and apply migrations for this table.

### 1.3 不做什么（剔除）

- [ ] No API router or HTTP endpoint in this issue — that belongs to the router step of #513.
- [ ] No seed data or data migration from legacy stores.
- [ ] No analytics service logic (enrichment lookup / aggregation) — deferred to #754.

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src python -c "from db.models.enrichment import CustomerEnrichment; print(CustomerEnrichment.__tablename__)"` → `customer_enrichment` exit 0]
- [指标 2：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0]
- [指标 3：`ruff check src/db/models/enrichment.py src/db/models/__init__.py` → 0 errors]
- [指标 4：`alembic show head` confirms revision creates `customer_enrichment` with `tenant_id`, `enriched_at`, `enrichment_data`]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — import and re-export `CustomerEnrichment` so Alembic sees it
  - `alembic/env.py` — add `from db.models import CustomerEnrichment` (or rely on __init__ re-export) if autogenerate misses it
- 要建：
  - `src/db/models/enrichment.py` — `CustomerEnrichment` ORM model
  - `alembic/versions/<id>_add_customer_enrichment.py` — creates `customer_enrichment` table
  - `tests/unit/conftest.py` — add `make_enrichment_handler(state)` if mock infrastructure is extended

### 2.3 缺什么

- [ ] `src/db/models/enrichment.py` — the ORM model is entirely absent; no `customer_enrichment` table can be created
- [ ] Alembic migration — without a migration, no `customer_enrichment` table exists in any environment
- [ ] Index on `enrichment_data` (JSONB) — without a GIN index, JSONB column queries will be full-table scans in production
- [ ] Unique constraint `(tenant_id, customer_id)` — without it, duplicate enrichment writes are silent and analytics results become non-deterministic
- [ ] Composite index `(tenant_id, enriched_at)` — without it, time-range tenant queries scan the full table

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/enrichment.py` | `CustomerEnrichment` ORM model with all required columns and indexes |
| `alembic/versions/<id>_add_customer_enrichment.py` | Alembic migration creating `customer_enrichment` table with corrected JSONB and TIMESTAMPTZ |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/__init__.py` | Add `from db.models.enrichment import CustomerEnrichment` and re-export |

### 3.3 新增能力

- **ORM model**：`CustomerEnrichment` in `src/db/models/enrichment.py` — columns: `id`, `tenant_id`, `customer_id`, `provider`, `enriched_at` (TIMESTAMPTZ), `enrichment_data` (JSONB), `created_at`, `updated_at`
- **Indexes**：
  - `CREATE UNIQUE INDEX uq_tenant_customer ON customer_enrichment (tenant_id, customer_id)`
  - `CREATE INDEX ix_tenant_enriched_at ON customer_enrichment (tenant_id, enriched_at)`
  - `CREATE INDEX ix_tenant_customer_enriched_at ON customer_enrichment USING GIN (tenant_id, enrichment_data)` — note: GIN on JSONB column
- **Alembic migration**：`alembic upgrade head` creates the table; `alembic downgrade -1` drops it cleanly

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSONB not JSON**：`enrichment_data` uses `JSONB` (binary JSON) because CRM analytics query patterns (key existence, containment, prefix search) require indexed access. Plain `JSON` stores text and does not support GIN/B-tree indexing in PostgreSQL.
- **GIN index on JSONB** (not separate expression index per analytics query) — GIN covers all standard JSONB operators (`@>`, `?`, `?&`, `?|`). A B-tree index on a cast expression would only cover the equality case.
- **Unique constraint `(tenant_id, customer_id)`** — enforces exactly-one-enrichment-record-per-customer within a tenant, eliminating silent duplicates in concurrent write scenarios.
- **No feature flag** — this is a pure schema addition; there is no runtime behaviour to toggle. Migration rollback is the backstop.

### 4.2 版本约束

No new external dependencies introduced.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must include `WHERE tenant_id = :tenant_id` (enforced by ORM model column + indexed constraint)
- `enrichment_data` column name is **not** `metadata` — `Base.metadata` (SQLAlchemy's `MetaData` object) conflicts with a class attribute named `metadata` on any `Base` subclass, causing a crash at class definition time
- Use `mapped_column(DateTime(timezone=True))` for `enriched_at`, `created_at`, `updated_at` — naive `DateTime` silently stores no timezone info in PostgreSQL, making `enriched_at` comparisons unreliable across time zones
- Import path must be `from db.models.enrichment import CustomerEnrichment` (PYTHONPATH=src), not `from src.db.models.enrichment`

### 4.4 已知坑

1. **Alembic autogenerate emits `JSON` instead of `JSONB`** → Symptom: `enrichment_data` column created as `JSON` type, GIN index rejected at migration apply time → Fix: manually replace `sa.JSON()` with `sa.JSONB()` in the generated migration
2. **Alembic autogenerate emits `DateTime` without `timezone=True`** → Symptom: `enriched_at` stored as `timestamp without time zone`; equality/range queries across UTC conversions are off by hour offsets → Fix: manually add `timezone=True` to `DateTime` in the migration for all timestamp columns
3. **Alembic autogenerate emits B-tree index on JSONB column** → Symptom: PostgreSQL rejects `CREATE INDEX ... ON customer_enrichment USING btree (enrichment_data)` with `operator class "jsonb_ops" is not compatible with btree` → Fix: replace with `USING GIN (enrichment_data)` — GIN is the correct index type for JSONB
4. **ORM model column named `metadata`** → Symptom: `TypeError: 'MetaData' object is not callable` at class definition time → Fix: use `event_metadata`, `enrichment_data`, or `payload` instead; `enrichment_data` is already chosen

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/db/models/enrichment.py`

Create the new model file with the `CustomerEnrichment` class.

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CustomerEnrichment(Base):
    __tablename__ = "customer_enrichment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", name="uq_customer_enrichment_tenant_customer"),
        Index("ix_customer_enrichment_tenant_enriched_at", "tenant_id", "enriched_at"),
        Index("ix_customer_enrichment_tenant_customer_gin", "tenant_id", "enrichment_data", postgresql_using="gin"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    enriched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enrichment_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

Note: `updated_at` should use `func.now()` or `text("now()")` in the migration for proper server-side default. The ORM `onupdate` callable is fine for SQLAlchemy ORM operations.

**完成判定**：`PYTHONPATH=src python -c "from db.models.enrichment import CustomerEnrichment; print('OK')"` → exit 0, no `ImportError` or `TypeError`

---

### Step 2: Update `src/db/models/__init__.py`

Add the model import so it is visible to Alembic's `env.py` (which imports the package, not individual modules).

In `src/db/models/__init__.py`, add:

```python
from db.models.enrichment import CustomerEnrichment
```

and add `CustomerEnrichment` to the `__all__` list if one exists.

**完成判定**：`PYTHONPATH=src python -c "from db.models import CustomerEnrichment; print('OK')"` → exit 0

---

### Step 3: Verify Alembic sees the model

Check that `alembic/env.py` imports `db.models` (or specifically `CustomerEnrichment`). If the import is already present via `from db.models import Base` or `from db.models import *`, Alembic will auto-detect the new table.

If not, add to the env.py imports block:

```python
from db.models import CustomerEnrichment  # noqa: F401
```

**完成判定**：`alembic current` runs without error (even if no migrations applied yet)

---

### Step 4: Prepare a clean `alembic_dev` database

Set up a clean DB per CLAUDE.md §Alembic Migrations so autogenerate sees a true diff.

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

**完成判定**：All commands exit 0 with no error output.

---

### Step 5: Run `alembic revision --autogenerate`

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic revision --autogenerate -m "add customer_enrichment"
```

**完成判定**：A new file `alembic/versions/<id>_add_customer_enrichment.py` is created.

---

### Step 6: Manually fix the generated migration

Open the generated migration and apply these corrections:

**a) JSON → JSONB**: Replace `sa.JSON()` with `sa.JSONB()` for `enrichment_data`.

**b) DateTime → DateTime(timezone=True)**: Ensure `enriched_at`, `created_at`, `updated_at` columns use `DateTime(timezone=True)` not plain `DateTime`.

**c) GIN index on JSONB**: The autogenerated B-tree index on `enrichment_data` must be replaced:

```python
# WRONG (autogenerate produces this):
# Index("ix_customer_enrichment_tenant_customer_gin", "enrichment_data")

# CORRECT:
Index(
    "ix_customer_enrichment_tenant_customer_gin",
    "enrichment_data",
    postgresql_using="gin",
)
```

Or alternatively create as a separate index:

```python
op.create_index(
    "ix_customer_enrichment_enrichment_data_gin",
    "customer_enrichment",
    ["enrichment_data"],
    postgresql_using="gin",
)
```

**d) Check the unique constraint and composite index** are present and correctly reference `tenant_id` and `customer_id`.

**完成判定**：`grep -c "JSONB" alembic/versions/<new_id>_add_customer_enrichment.py` → 1 or more; `grep -c "timezone=True" alembic/versions/<new_id>_add_customer_enrichment.py` → ≥ 3; `grep "postgresql_using=\"gin\"" alembic/versions/<new_id>_add_customer_enrichment.py` → 1 or more

---

### Step 7: Verify migration applies and rolls back cleanly

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：All three commands exit 0. No PostgreSQL error about JSONB/GIN/operator class.

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models import CustomerEnrichment"` → exit 0 (model imports cleanly)
- [ ] `ruff check src/db/models/enrichment.py src/db/models/__init__.py` → 0 errors
- [ ] `alembic upgrade head` → exit 0 with no error (creates `customer_enrichment` table)
- [ ] `alembic downgrade -1` → exit 0 (drops `customer_enrichment` table)
- [ ] `alembic upgrade head` → exit 0 (recreates cleanly)
- [ ] `ruff check alembic/versions/<id>_add_customer_enrichment.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces invalid index syntax for GIN on JSONB and migration fails to apply | 中 | 高 | Step 6 manual fixes are deterministic; if a fix is missed, rerun autogenerate after correcting the ORM model's `__table_args__` |
| JSONB column created as plain JSON causing downstream JSONB-operator queries to error | 中 | 中 | Run `ALTER TABLE customer_enrichment ALTER COLUMN enrichment_data TYPE JSONB USING enrichment_data::JSONB` as a corrective migration |
| Migration applied to shared dev DB while another branch also runs migration (conflict) | 低 | 中 | Alembic is safe for concurrent upgrades; the second runner will exit 0 once the first completes. Schema conflict is impossible with proper `alembic_lock` table usage |
| Downgrade in production accidentally drops table with real data | 低 | 高 | Not applicable in this issue scope (no prod migration step); future production migration must use `alembic upgrade head` only, never `downgrade` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/enrichment.py src/db/models/__init__.py alembic/versions/
git commit -m "feat(models): add CustomerEnrichment ORM model + alembic migration (#753)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(models): add CustomerEnrichment ORM model (#753)" --body "Closes #753

## What
- Add `CustomerEnrichment` ORM model in `src/db/models/enrichment.py`
- Alembic migration creates `customer_enrichment` table with JSONB + GIN index
- Import model in `src/db/models/__init__.py`

## Test plan
- [x] \`alembic upgrade head && alembic downgrade -1 && alembic upgrade head\` exits 0
- [x] \`ruff check src/db/models/\` → 0 errors"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/customer.py` — existing CRM model with tenant_id + indexes for conventions
- 父 issue / 关联：#513

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
