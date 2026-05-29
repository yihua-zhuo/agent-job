# Analytics · Add model versioning and tracking to prediction records

| 元数据 | 值 |
|---|---|
| Issue | #576 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0575-add-churn-prediction-model-and-records](../50-automation/0575-add-churn-prediction-model-and-records.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Currently, churn prediction records carry no metadata about which model version produced them. As the model evolves, it becomes impossible to trace a specific prediction back to the training run, feature config, or metrics that were live at the time. This makes model auditing, A/B analysis, and rollback decisions impossible. Without explicit model versioning, every prediction is effectively opaque.

### 1.2 做完后

- **用户视角**：No direct user-visible change — this is a pure data/infra enhancement.
- **开发者视角**：Batch jobs and on-demand predictors can call `ChurnModelService.get_current_model()` to stamp predictions with the live model version. `log_model_version()` allows a training pipeline to register a new version. The `ModelVersion` table provides an auditable history of every deployed model including its feature config and accuracy metrics.

### 1.3 不做什么（剔除）

- [ ] Retraining pipeline / model training code — only versioning and recording, not training
- [ ] A/B routing or model-selection logic in the serving layer — stamping is write-only
- [ ] Backfill of existing `ChurnPrediction` records with historical model versions

### 1.4 关键 KPI

- `pytest tests/unit/test_churn_model_service.py -v` → ≥ 5 passed
- `pytest tests/integration/test_churn_model_version_integration.py -v` → ≥ 4 passed
- `ruff check src/services/churn_model_service.py src/db/models/churn_prediction.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/churn_prediction.py` — existing `ChurnPrediction` model likely has basic fields (tenant_id, customer_id, score, predicted_at). Confirm whether `model_name`, `model_version`, `training_data_start_date` columns already exist.

TBD - 待验证：`src/services/churn_prediction_service.py` or equivalent — batch job that writes `ChurnPrediction` records; likely in a jobs/ or services/ directory.

TBD - 待验证：`src/api/routers/churn.py` or equivalent — if a router exposes prediction endpoints, it may need to wire the model version stamp.

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/churn_prediction.py` — add `model_name`, `model_version`, `training_data_start_date` columns
  - `tests/unit/test_churn_prediction.py` — extend unit tests for new columns
  - `tests/integration/test_churn_prediction_integration.py` — extend integration tests for new columns
- 要建：
  - `src/db/models/model_version.py` — `ModelVersion` ORM model
  - `src/services/churn_model_service.py` — `ChurnModelService` with `get_current_model()`, `log_model_version()`
  - `alembic/versions/<id>_add_model_version_and_churn_prediction_fields.py` — migration for both the new table and the new columns on `churn_prediction`
  - `tests/unit/test_churn_model_service.py` — unit tests for `ChurnModelService`
  - `tests/integration/test_churn_model_version_integration.py` — integration tests for the full versioning flow

### 2.3 缺什么

- [ ] No `ModelVersion` table — model metadata (name, version, trained_at, feature_config, metrics) has nowhere to be persisted
- [ ] `ChurnPrediction` records are not stamped with model version at write time
- [ ] No service layer to retrieve the current live model or to log a new version
- [ ] Batch job has no hook to call a version-stamping service

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/model_version.py` | `ModelVersion` ORM model (id, model_name, version, trained_at, feature_config JSON, metrics JSON) |
| `src/services/churn_model_service.py` | `ChurnModelService` with `get_current_model()` / `log_model_version()` |
| `alembic/versions/<id>_add_model_version_and_churn_prediction_fields.py` | Creates `model_version` table; adds model_name / model_version / training_data_start_date columns to `churn_prediction` |
| `tests/unit/test_churn_model_service.py` | Unit tests for `ChurnModelService` methods |
| `tests/integration/test_churn_model_version_integration.py` | Integration tests for the versioning flow end-to-end |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/churn_prediction.py` | Add `model_name: Mapped[str]`, `model_version: Mapped[str]`, `training_data_start_date: Mapped[datetime \| None]` columns; add index on `(model_name, model_version)` |
| `src/services/churn_prediction_service.py` (or batch job file) | Call `ChurnModelService.get_current_model()` and stamp prediction records with version fields |
| `tests/unit/test_churn_prediction.py` | Add test cases for new columns |
| `tests/integration/test_churn_prediction_integration.py` | Add test cases asserting columns are persisted correctly |

### 3.3 新增能力

- **ORM model**：`ModelVersion` in `src/db/models/model_version.py`
- **ORM columns**：added to `ChurnPrediction` — `model_name`, `model_version`, `training_data_start_date`
- **Service method**：`ChurnModelService.get_current_model(self, tenant_id: int) -> ModelVersion`
- **Service method**：`ChurnModelService.log_model_version(self, version: ModelVersion, tenant_id: int) -> ModelVersion`
- **Migration**：`alembic upgrade head` creates `model_version` table with composite index on `(tenant_id, model_name, version)`
- **Batch integration**：prediction batch job stamps `ChurnPrediction` records with `get_current_model()` result

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Store feature_config and metrics as JSONB, not as a separate relation** → avoids schema proliferation for semi-structured config; SQLAlchemy JSONB column maps cleanly to `dict` Python type with no ORM overhead.
- **Write model version stamp at prediction time via service call, not as a raw SQL update in the batch job** → keeps business logic in the service layer; the batch job only calls `ChurnModelService.get_current_model()`, never constructs SQL directly.
- **Add composite index on `(tenant_id, model_name, version)` in model_version table** → `get_current_model()` queries by `tenant_id + model_name` ordered by `trained_at DESC LIMIT 1`; the index covers the lookup without a separate unique constraint on `(tenant_id, model_name)` which would prevent re-training a model.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `alembic` | `>=1.13` | Required for `alembic/env.py` async `asyncpg` support |

### 4.3 兼容性约束

- Multi-tenant: every SQL query must include `WHERE tenant_id = :tenant_id`; `model_version.tenant_id` must be a non-null indexed column.
- `ModelVersion` inherits from `Base`; table name `model_version` maps to `model_version` table in PostgreSQL.
- `ChurnPrediction.model_name` / `model_version` / `training_data_start_date` are nullable to support existing rows written before this migration; `get_current_model()` always writes non-null values for new records.
- Service returns ORM objects; router serializes via `.to_dict()` — do **not** call `.to_dict()` inside the service.
- Service raises `AppException` subclasses (`NotFoundException` if no model version exists for a tenant); do **not** return `ApiResponse.error()`.

### 4.4 已知坑

1. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()`** → after autogenerate, manually replace `JSON().with_variant(sqlite.JSON(), "sqlite")` pattern with `JSONB()` and add `.with_variant(JSON(), "sqlite")` for cross-database test compatibility.
2. **Alembic autogenerate drops `timezone=True` on DateTime columns** → always verify `trained_at` column has `timezone=True` in the migration; `sa.DateTime(timezone=True)` is required for PostgreSQL TIMESTAMPTZ.
3. **`metadata` column name on a Base subclass collides with `Base.metadata`** → the new JSON column on `ModelVersion` must be named `feature_config` and `metrics`, not `metadata` — see CLAUDE.md "SQLAlchemy do not name a column `metadata`".

---

## 5. 实现步骤（按顺序）

### Step 1: Create ModelVersion ORM model

Define `ModelVersion` in `src/db/models/model_version.py`.

Columns:
- `id: Mapped[int]` — primary key, auto-increment
- `tenant_id: Mapped[int]` — non-null, indexed (composite index with model_name + version)
- `model_name: Mapped[str]` — non-null (e.g. `"churn_v1"`)
- `version: Mapped[str]` — non-null (e.g. `"2026-05-01-001"`)
- `trained_at: Mapped[datetime]` — non-null, timezone-aware
- `feature_config: Mapped[dict]` — JSONB column, stores feature names and params
- `metrics: Mapped[dict]` — JSONB column, stores `{"accuracy": 0.87, "precision": 0.84, "recall": 0.80}`
- `created_at: Mapped[datetime]` — auto-set on insert

Unique constraint: `(tenant_id, model_name, version)` to prevent duplicate log entries.

```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ModelVersion(Base):
    __tablename__ = "model_version"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    feature_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "model_name", "version", name="uq_model_version"),
        Index("ix_model_version_tenant_model", "tenant_id", "model_name", version),
    )
```

Register in `alembic/env.py` if not already imported by the existing import chain.

**完成判定**：`ruff check src/db/models/model_version.py` → 0 errors / `python -c "from db.models.model_version import ModelVersion; print(ModelVersion.__tablename__)"` exits 0

---

### Step 2: Add model version columns to ChurnPrediction

Extend `src/db/models/churn_prediction.py` with three new columns:

- `model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)`
- `model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)`
- `training_data_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)`

Add index: `Index("ix_churn_prediction_model_version", "model_name", "model_version")` — useful for audit queries that filter by model.

**完成判定**：`ruff check src/db/models/churn_prediction.py` → 0 errors

---

### Step 3: Create ChurnModelService

Create `src/services/churn_model_service.py` with the service class.

```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.model_version import ModelVersion


class ChurnModelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_model(
        self, model_name: str, tenant_id: int
    ) -> Optional[ModelVersion]:
        """Return the most recently trained version for a given model name."""
        stmt = (
            select(ModelVersion)
            .where(ModelVersion.tenant_id == tenant_id)
            .where(ModelVersion.model_name == model_name)
            .order_by(desc(ModelVersion.trained_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def log_model_version(
        self,
        model_name: str,
        version: str,
        trained_at: datetime,
        feature_config: dict,
        metrics: dict,
        tenant_id: int,
    ) -> ModelVersion:
        """Create a new ModelVersion record."""
        record = ModelVersion(
            tenant_id=tenant_id,
            model_name=model_name,
            version=version,
            trained_at=trained_at,
            feature_config=feature_config,
            metrics=metrics,
        )
        self.session.add(record)
        await self.session.flush()
        return record
```

**完成判定**：`ruff check src/services/churn_model_service.py` → 0 errors / `python -c "from services.churn_model_service import ChurnModelService; print(ChurnModelService)"` exits 0

---

### Step 4: Generate Alembic migration

Spin up a disposable `alembic_dev` database (see CLAUDE.md §Alembic Migrations), then:

```
alembic revision --autogenerate -m "add_model_version_table_and_churn_prediction_fields"
```

After autogenerate, manually correct:
- `feature_config` column: replace `sa.JSON()` with `sa.JSONB().with_variant(sa.JSON(), "sqlite")`
- `metrics` column: same JSONB fix
- `trained_at`: ensure `timezone=True` is present
- `training_data_start_date` on `churn_prediction`: ensure `timezone=True`

Verify the migration:
```
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Second autogenerate against `alembic_dev` should produce an empty diff (delete the drift-check migration if it has only `pass` in up/down).

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0

---

### Step 5: Wire model version stamp into prediction batch job

TBD - 待验证：Locate the batch job file that writes `ChurnPrediction` records (likely in `src/jobs/` or invoked via a scheduler). At the point where a prediction record is created, inject `ChurnModelService` and stamp:

```python
svc = ChurnModelService(session)
current = await svc.get_current_model("churn_v1", tenant_id)
if current:
    prediction.model_name = current.model_name
    prediction.model_version = current.version
    prediction.training_data_start_date = current.trained_at
```

Do **not** call `.to_dict()` inside the batch job. If the batch job runs in a loop, reuse a single `ChurnModelService` instance per tenant to avoid repeated instantiation.

**完成判定**：`ruff check src/jobs/` or the identified batch job file → 0 errors / all existing tests still pass

---

### Step 6: Write unit tests for ChurnModelService

Create `tests/unit/test_churn_model_service.py`. Use `make_mock_session` and state handlers. Test cases:

1. `get_current_model` returns latest version when multiple exist for the same model name
2. `get_current_model` returns `None` when no version is logged for the tenant/model combination
3. `log_model_version` creates a record and returns the ORM object with all fields populated
4. Service raises no exceptions on happy path (caller handles `None` from `get_current_model`)
5. All queries filter by `tenant_id` (verify via mock handler call inspection)

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_model_service.py -v` → 5 passed

---

### Step 7: Write integration tests for versioning flow

Create `tests/integration/test_churn_model_version_integration.py`. Use `db_schema`, `tenant_id`, `async_session` fixtures.

Test cases:

1. `log_model_version` persists a record and it can be retrieved with `get_current_model`
2. `get_current_model` returns the most recent `trained_at` when multiple versions exist
3. `ChurnPrediction` records written by the batch job contain the stamped `model_name`, `model_version`, `training_data_start_date`
4. Migration can be upgraded and downgraded cleanly (separate test, uses `db_schema` fixture auto-TRUNCATE)

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_model_version_integration.py -v` → 4 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/model_version.py src/db/models/churn_prediction.py src/services/churn_model_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_model_service.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_churn_model_version_integration.py -v` → ≥ 4 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0
- [ ] All existing unit tests still pass: `PYTHONPATH=src pytest tests/unit/ -v` → no new failures
- [ ] All existing integration tests still pass: `PYTHONPATH=src pytest tests/integration/ -v` → no new failures

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Migration adds nullable columns to `churn_prediction`; existing batch jobs that construct INSERT statements without those columns will silently drop them | 低 | 中 | Columns are nullable by design — no backfill required; batch job change is additive only |
| JSONB columns with large `feature_config` dict cause query performance issues on `model_version` lookups | 低 | 中 | Composite index on `(tenant_id, model_name, version)` is created in the same migration to cover the lookup path; monitor `pg_stats` after deploy |
| `ChurnModelService.get_current_model()` returns `None` for a tenant that has no logged versions | 低 | 中 | Batch job checks for `None` and skips stamping; prediction record is written with nulls — no crash, no data loss. Training pipeline must call `log_model_version` before the model goes live |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/model_version.py src/db/models/churn_prediction.py \
       src/services/churn_model_service.py \
       alembic/versions/<id>_add_model_version_and_churn_prediction_fields.py \
       tests/unit/test_churn_model_service.py \
       tests/integration/test_churn_model_version_integration.py
git commit -m "feat(analytics): add model versioning to ChurnPrediction records"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#576): add model versioning and tracking to prediction records" --body "Closes #576"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Parent / 关联：#51 (analytics foundation parent), #575 (churn prediction model and records)
- SQLAlchemy async: `select(ModelVersion).order_by(desc(ModelVersion.trained_at)).limit(1)` pattern for "latest per group"
- Alembic JSONB: see CLAUDE.md §4.4 Known Gotchas — always verify `timezone=True` on DateTime and `JSONB` not `JSON` after autogenerate

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
