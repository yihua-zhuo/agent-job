# ChurnPrediction 模型 · 创建 ORM 与迁移

| 元数据 | 值 |
|---|---|
| Issue | #815 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [ChurnNotificationService 占位桩](../60-analytics/0816-add-churnnotificationservice-placeholder-stub.md), [Churn batch job 实现](../60-analytics/0817-implement-churn-batch-job-py-with-batch-logic-threshold-dete.md), [Batch job 集成测试](../60-analytics/0818-write-integration-test-for-batch-job-and-threshold-alert.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently has no persistence layer for churn prediction outputs. Downstream boards (notification service, batch job, integration tests) all need a stable table to read from and write to. Without this model, there is no place to store per-tenant, per-customer churn scores, and any analytics/retention feature is blocked at the data layer. This is the schema foundation for the entire churn analytics sub-epic (#575).

### 1.2 做完后

- **User perspective**: No user-visible change — pure infrastructure/DB layer change. End users will only see effects once the downstream notification service and batch job boards are implemented.
- **Developer perspective**: A new `ChurnPrediction` ORM model is importable from `db.models`, the `churn_predictions` table exists in PostgreSQL with correct types (`JSONB` for metadata, `TIMESTAMPTZ` for timestamps), and a reversible Alembic migration manages the schema lifecycle. The model supports multi-tenant queries via `tenant_id` filtering.

### 1.3 不做什么（剔除）

- [ ] No service class for churn CRUD operations (handled by #816 and #817)
- [ ] No router or API endpoint (not in scope for this board)
- [ ] No batch/scoring logic — this board only persists the table
- [ ] No backfill of historical predictions — table starts empty
- [ ] No indexes beyond the standard `tenant_id` index and implicit FK indexes (can be added later if query patterns warrant)

### 1.4 关键 KPI

- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all three commands exit 0
- `ruff check src/db/models/churn_prediction.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models import ChurnPrediction"` → exit 0, no ImportError
- `alembic revision --autogenerate -m 'drift_check'` after applying migration → empty diff (no residual drift)
- `churn_predictions` table exists in PostgreSQL with columns: `id`, `tenant_id`, `customer_id`, `score`, `predicted_at` (TIMESTAMPTZ), `previous_score` (nullable), `prediction_metadata` (JSONB)

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：N/A — 新建模块

This is a greenfield schema addition. No existing `ChurnPrediction` model or `churn_predictions` table exists in the codebase. The `db/models/` directory and `alembic/env.py` are the integration points.

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/__init__.py`](../../../src/db/models/__init__.py) — Add `ChurnPrediction` to the model exports
  - [`alembic/env.py`](../../../alembic/env.py) — Add `from db.models.churn_prediction import ChurnPrediction` so autogen sees the model
- 要建：
  - `src/db/models/churn_prediction.py` — New ORM model definition
  - `alembic/versions/<autogen_revision>_create_churn_predictions_table.py` — New reversible migration
  - `tests/unit/test_churn_prediction_model.py` — Unit tests for model import and basic structure

### 2.3 缺什么

- [ ] No `ChurnPrediction` ORM model — downstream boards have nowhere to write/read churn scores
- [ ] No `churn_predictions` table in PostgreSQL — no persistence for analytics outputs
- [ ] No migration managing the `churn_predictions` schema lifecycle — schema changes would be untracked
- [ ] No multi-tenant indexing on `churn_predictions.tenant_id` — tenant isolation at the query level would be unindexed

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/churn_prediction.py` | `ChurnPrediction` SQLAlchemy ORM model |
| `alembic/versions/<rev>_create_churn_predictions_table.py` | Reversible migration creating the `churn_predictions` table |
| `tests/unit/test_churn_prediction_model.py` | Unit tests for model structure and importability |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/__init__.py`](../../../src/db/models/__init__.py) | Add `ChurnPrediction` import and export |
| [`alembic/env.py`](../../../alembic/env.py) | Add `from db.models.churn_prediction import ChurnPrediction` for autogen discovery |

### 3.3 新增能力

- **ORM model**: `ChurnPrediction` in `src/db/models/churn_prediction.py` with columns: `id` (PK), `tenant_id` (indexed), `customer_id` (FK to `customers`), `score` (Float), `predicted_at` (DateTime with `timezone=True`), `previous_score` (Float, nullable), `prediction_metadata` (JSON via `JSONB` dialect)
- **Migration**: `alembic upgrade head` creates `churn_predictions` table; `alembic downgrade -1` drops it; both must be reversible
- **Multi-tenant**: `tenant_id` column with index for all queries
- **Model importability**: `from db.models import ChurnPrediction` works without ImportError

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Column `prediction_metadata` uses `JSON` (mapped to `JSONB` in PostgreSQL)**: SQLAlchemy's `JSON` type is dialect-aware — on PostgreSQL it maps to `JSONB`, which supports indexing and efficient querying. Using `sa.JSONB()` directly in the model is also valid, but `JSON` with the `postgresql.JSONB` variant is the idiomatic SQLAlchemy 2.x approach for cross-database compatibility. Autogenerate may emit `sa.JSON()` — this must be manually changed to `postgresql.JSONB()` in the migration file.
- **`predicted_at` uses `DateTime(timezone=True)`**: Must be `TIMESTAMPTZ` in PostgreSQL to correctly store UTC-aware timestamps. Autogenerate tends to emit `sa.DateTime()` without `timezone=True` — manually fix this.
- **No `UniqueConstraint` on `(tenant_id, customer_id, predicted_at)`**: Predictions are append-only — multiple predictions per customer are expected (a time series of scores). No unique constraint needed.

### 4.2 版本约束

No new external dependencies introduced. This board uses only existing libraries: SQLAlchemy 2.x async, Alembic, PostgreSQL `asyncpg` driver.

### 4.3 兼容性约束

- Multi-tenant: every future SQL query against `churn_predictions` must include `WHERE tenant_id = :tenant_id` (see CLAUDE.md §Multi-Tenancy)
- The `prediction_metadata` column name must NOT be `metadata` — it must be `prediction_metadata` (or `event_metadata` / `payload` / `attrs`) because `Base.metadata` is a reserved attribute on SQLAlchemy declarative Base. Using `metadata` as a column name will crash at class definition.
- Service return values: not applicable for this board (no service created). When services are added in #816/#817, they must return ORM objects, not `.to_dict()`.
- Migration must be reversible: `downgrade()` must drop the `churn_predictions` table

### 4.4 已知坑

1. **Autogen emits `sa.JSON()` instead of `sa.JSONB()`** → After autogenerate, manually edit the migration file to replace `sa.Column('prediction_metadata', sa.JSON(), ...)` with `sa.Column('prediction_metadata', postgresql.JSONB(), ...)`. Add `from sqlalchemy.dialects import postgresql` at the top if not present.
2. **Autogen drops `timezone=True` on DateTime** → After autogenerate, manually verify `sa.Column('predicted_at', sa.DateTime(), ...)` has `timezone=True`. Fix: `sa.Column('predicted_at', sa.DateTime(timezone=True), ...)`. Run `alembic upgrade head` and check the actual column type with `\d churn_predictions` in psql.
3. **Model not registered with Alembic** → If `alembic/env.py` does not `import` the model module, autogen will produce an empty diff. Must add `from db.models.churn_prediction import ChurnPrediction` to `env.py`.
4. **PYTHONPATH not set** → `alembic` commands and Python imports require `export PYTHONPATH=src` before running. Without it, `from db.models...` will fail with `ModuleNotFoundError`.
5. **Column name `metadata` collision** → Never name a column `metadata` on a `Base` subclass. It collides with `Base.metadata` (the `MetaData` object) and crashes at class definition. The issue body correctly specifies `prediction_metadata` — keep it.

---

## 5. 实现步骤（按顺序）

### Step 1: Create the ChurnPrediction ORM model file

Create the new model file with all required columns, `tenant_id` index, and proper type annotations using SQLAlchemy 2.x `Mapped` / `mapped_column` syntax.

操作：
- a) Create `src/db/models/churn_prediction.py`
- b) Define class `ChurnPrediction(Base)` with `__tablename__ = "churn_predictions"`
- c) Add columns: `id` (Integer PK), `tenant_id` (Integer, nullable=False, index=True), `customer_id` (Integer, nullable=False, index=True), `score` (Float, nullable=False), `predicted_at` (DateTime(timezone=True), nullable=False), `previous_score` (Float, nullable=True), `prediction_metadata` (JSON, nullable=True)
- d) Use `Mapped[T]` and `mapped_column(...)` type annotations per SQLAlchemy 2.x convention

示例代码：

```python
from datetime import datetime
from sqlalchemy import Float, Integer, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChurnPrediction(Base):
    __tablename__ = "churn_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

**完成判定**: `PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPrediction; print(ChurnPrediction.__tablename__)"` → prints `churn_predictions` with exit 0

### Step 2: Export the model from `db/models/__init__.py`

Make `ChurnPrediction` importable via `from db.models import ChurnPrediction`.

操作：
- a) Read [`src/db/models/__init__.py`](../../../src/db/models/__init__.py) to see existing export pattern
- b) Add `from db.models.churn_prediction import ChurnPrediction` (or add to existing import list / `__all__` as appropriate)

**完成判定**: `PYTHONPATH=src python -c "from db.models import ChurnPrediction; print(ChurnPrediction)"` → exit 0, prints `<class 'db.models.churn_prediction.ChurnPrediction'>`

### Step 3: Register the model in `alembic/env.py`

Ensure Alembic's autogenerate can see the new model.

操作：
- a) Read [`alembic/env.py`](../../../alembic/env.py) to find the model import block
- b) Add `from db.models.churn_prediction import ChurnPrediction` alongside other model imports

**完成判定**: `grep -q "churn_prediction" alembic/env.py` → exit 0

### Step 4: Autogenerate the migration

Run Alembic autogen against a clean `alembic_dev` database (not the test DB).

操作：
- a) Set up env vars: `export PYTHONPATH=src` and `export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"`
- b) Bring DB to current head: `alembic upgrade head`
- c) Run: `alembic revision --autogenerate -m "create_churn_predictions_table"`
- d) Note the generated revision file path (e.g. `alembic/versions/<rev>_create_churn_predictions_table.py`)

**完成判定**: New file exists in `alembic/versions/` with filename matching `*_create_churn_predictions_table.py`; `upgrade()` function contains `op.create_table('churn_predictions', ...)`

### Step 5: Manually fix autogen issues

Inspect the generated migration and fix known autogen problems.

操作：
- a) Open the generated migration file
- b) Find `sa.JSON()` for `prediction_metadata` → replace with `postgresql.JSONB()`
- c) Find `sa.DateTime()` for `predicted_at` → ensure `timezone=True` is present
- d) If `from sqlalchemy.dialects import postgresql` is not imported at the top, add it
- e) Verify `downgrade()` drops the table: `op.drop_table('churn_predictions')`

**完成判定**: Migration file contains `postgresql.JSONB()` for `prediction_metadata`; `predicted_at` column has `timezone=True`; `downgrade()` calls `op.drop_table('churn_predictions')`

### Step 6: Verify migration roundtrip

Apply the migration, revert it, and re-apply to confirm reversibility.

操作：
- a) `export PYTHONPATH=src`
- b) `alembic upgrade head` → expect exit 0
- c) `alembic downgrade -1` → expect exit 0
- d) `alembic upgrade head` → expect exit 0
- e) Optionally verify schema in psql: `\d churn_predictions` → should show `prediction_metadata` as `jsonb` and `predicted_at` as `timestamp with time zone`

**完成判定**: All three Alembic commands exit 0

### Step 7: Confirm no residual drift

Run a second autogenerate to verify the migration captured all model changes.

操作：
- a) `alembic revision --autogenerate -m "drift_check"`
- b) If the new file has `pass` in both `upgrade()` and `downgrade()`, delete it (no drift)
- c) If the new file contains actual schema changes, the first migration was incomplete — go back to Step 5 and fix

**完成判定**: Either no `drift_check` file remains, or the file contains only `pass` in `upgrade()` and `downgrade()`

### Step 8: Write unit tests and run lint

Create a unit test file and run ruff to ensure code quality.

操作：
- a) Create `tests/unit/test_churn_prediction_model.py` with at minimum: (1) test that `ChurnPrediction` imports without error, (2) test that `__tablename__` is `"churn_predictions"`, (3) test that all required columns exist with correct types/nullability
- b) Run: `export PYTHONPATH=src && ruff check src/db/models/churn_prediction.py`
- c) Run: `export PYTHONPATH=src && pytest tests/unit/test_churn_prediction_model.py -v`
- d) Run: `export PYTHONPATH=src && ruff check src/`

**完成判定**: `ruff check src/db/models/churn_prediction.py` → 0 errors; `pytest tests/unit/test_churn_prediction_model.py -v` → all tests passed

---

## 6. 验收

- [ ] `export PYTHONPATH=src && ruff check src/db/models/churn_prediction.py` → 0 errors
- [ ] `export PYTHONPATH=src && python -c "from db.models import ChurnPrediction"` → exit 0, no ImportError
- [ ] `export PYTHONPATH=src && pytest tests/unit/test_churn_prediction_model.py -v` → all tests passed (minimum 3 passed)
- [ ] `export PYTHONPATH=src && ruff check src/` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all three exit 0
- [ ] Migration file contains `postgresql.JSONB()` (not `sa.JSON()`) for `prediction_metadata`
- [ ] Migration file has `timezone=True` on `predicted_at` DateTime column
- [ ] `alembic revision --autogenerate -m "drift_check"` after applying migration → produces empty diff (no residual drift)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogen produces incomplete migration (missing `JSONB` or `timezone=True`) | 高 | 中 | Manually edit the migration file before applying; verify with `\d churn_predictions` in psql. Run drift-check autogen to confirm no residual differences. |
| Migration applied to wrong database (test DB instead of `alembic_dev`) | 中 | 中 | Always set `DATABASE_URL` explicitly before running autogen. Never point autogen at the integration test DB (it's at model state via `create_all`). |
| `metadata` column name collision with `Base.metadata` | 低 | 高 | If accidentally used, class definition crashes immediately. Fix: rename column to `prediction_metadata` (already specified by issue body). |
| `env.py` not updated, autogen sees empty diff | 中 | 中 | Always run a drift-check autogen after the first migration. If empty, the model is not registered — add the import to `env.py` and regenerate. |
| Downstream boards (#816-#818) blocked by schema changes | 低 | 低 | This board is foundational; once merged, downstream boards can proceed. No partial state to roll back — the table either exists or doesn't. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/churn_prediction.py \
        src/db/models/__init__.py \
        alemic/env.py \
        alembic/versions/*_create_churn_predictions_table.py \
        tests/unit/test_churn_prediction_model.py
git commit -m "feat(db): add ChurnPrediction model and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(db): add ChurnPrediction model and migration" --body "Closes #815"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Parent issue / sub-epic: #575
- Sibling boards (downstream consumers of this model):
  - [ChurnNotificationService 占位桩](../60-analytics/0816-add-churnnotificationservice-placeholder-stub.md)
  - [Churn batch job 实现](../60-analytics/0817-implement-churn-batch-job-py-with-batch-logic-threshold-dete.md)
  - [Batch job 集成测试](../60-analytics/0818-write-integration-test-for-batch-job-and-threshold-alert.md)
- SQLAlchemy 2.x Mapped/mapped_column: https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
- Alembic autogen: https://alembic.sqlalchemy.org/en/latest/autogenerate.html

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-07 | 创建 | TBD |
