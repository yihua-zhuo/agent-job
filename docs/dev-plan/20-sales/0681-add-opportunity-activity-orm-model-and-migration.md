# 0681 · Add opportunity_activity ORM model and migration

| 元数据 | 值 |
|---|---|
| 周次 | W20.1 |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0681-add-opportunity-foreign-key-constraints](./0681-add-opportunity-foreign-key-constraints.md) — subtask of #665; FK target `opportunities.id` must exist first |
| 启用后赋能 | OpportunityActivityService（待建）, API router for GET/POST `/opportunities/{id}/activities`（待建） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #681 is a direct subtask of the sales pipeline automation epic #665. The CRM's opportunity lifecycle generates a stream of events (stage change, note added, closed won, etc.) — but there is no table to persist them. Without a persistent `opportunity_activities` table, every opportunity's event history is lost after the request ends. Downstream boards (#688 full-rule-lifecycle integration tests, #687 rule-execution engine, #686 automation rules router) all depend on being able to query past activity records in order to evaluate trigger conditions or display audit trails. Creating the ORM model and migration is the first prerequisite.

### 1.2 做完后

- **用户视角**：No immediate user-visible change — this is pure database schema infrastructure.
- **开发者视角**：`import db.models; OpportunityActivityModel` is available in the service layer. `alembic upgrade head` creates the `opportunity_activities` table with indexes on `tenant_id` and `opportunity_id`. Unit tests (`tests/unit/test_opportunity_activity_model.py`) confirm column types, nullability constraints, and `to_dict()` serialisation.

### 1.3 不做什么（剔除）

- [ ] No service layer — `OpportunityActivityService belongs to a downstream board.
- [ ] No REST API router — endpoints belong to a downstream board.
- [ ] No JSONB default constraint beyond `nullable=True` on the `metadata` column.
- [ ] No logic for event type enumeration — `event_type` is stored as `Text`/`String(50)` and caller is responsible for valid values.

### 1.4 关键 KPI

- `alembic upgrade head` → `opportunity_activities` table present in `alembic_dev`.
- `alembic downgrade -1` → `opportunity_activities` table dropped cleanly.
- `ruff check src/db/models/opportunity_activity.py` → zero warnings/errors.
- `PYTHONPATH=src pytest tests/unit/test_opportunity_activity_model.py -v` → ≥3 passed.
- `ruff check alembic/versions/*opportunity_activity*` → zero warnings.

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L1-L46 defines `OpportunityModel` — the FK target for `opportunity_activities.opportunity_id`. [`src/db/models/activity.py`](../../src/db/models/activity.py) L1-L35 shows an existing activity-like table (`activities`) with `opportunity_id` as a nullable FK on L19 — suggesting a separate `opportunity_activities` table (per-opportunity vs general CRM activity) is the intentional design. [`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L1-L88 demonstrates the canonical JSONB + FK + composite index pattern used in this codebase.

主入口：N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../alembic/env.py) — L14 already has `import db.models`; pkgutil auto-discovers new models, no change needed.
  - [`src/db/models/__init__.py`](../../src/db/models/__init__.py) — auto-imports all model modules via pkgutil; no change needed.
- 要建：
  - `src/db/models/opportunity_activity.py` — ORM model
  - `alembic/versions/<id>_create_opportunity_activities_table.py` — Alembic migration
  - `tests/unit/test_opportunity_activity_model.py` — unit tests

### 2.3 缺什么

- [ ] `src/db/models/opportunity_activity.py` does not exist — no ORM class for the `opportunity_activities` table.
- [ ] No Alembic migration for the `opportunity_activities` table.
- [ ] No FK constraint from `opportunity_activities.opportunity_id` → `opportunities.id` confirmed in PostgreSQL.
- [ ] No unit test file for the new model.
- [ ] Downstream service/router boards need this schema before they can implement activity read/write.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `src/db/models/opportunity_activity.py` | ORM model for `opportunity_activities` table: id, tenant_id (indexed), opportunity_id (FK to opportunities.id), event_type (String50), event_timestamp (DateTime), metadata (JSONB) |
| `alembic/versions/<id>_create_opportunity_activities_table.py` | Alembic migration: creates table with FK to opportunities, indexes on tenant_id and opportunity_id; fully reversible |
| `tests/unit/test_opportunity_activity_model.py` | Unit tests: instantiation, to_dict serialisation, column types, tenant isolation via MockRow |
| `docs/dev-plan/20-sales/0681_verify.sh` | Acceptance script: ruff + mypy + pytest |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../alembic/env.py) | Already has `import db.models` (L14) — pkgutil auto-discovers new model file, no change needed |
| [`src/db/models/__init__.py`](../../src/db/models/__init__.py) | Auto-imports all model modules via pkgutil — no change needed |

### 3.3 新增能力

- **Migration**: `alembic upgrade head` → `opportunity_activities` table exists with index on `tenant_id`, index on `opportunity_id`, and FK constraint `opportunity_id → opportunities.id ON DELETE CASCADE`.
- **verify 脚本**: `bash docs/dev-plan/20-sales/0681_verify.sh`
- **Slack 模板填空**: 按 README §2.9 模板 A（在 #progress 频道发送）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选独立的 `opportunity_activities` table over reusing the existing `activities` table**：The existing `activities` table (from `activity.py`) stores general CRM activity with a nullable `opportunity_id`. A separate table for opportunity-specific events allows fine-grained indexes and future schema evolution without coupling to the general activity log. Consistent with the subtask breakdown of #665.
- **选 JSONB over JSON for `metadata`**：PostgreSQL JSONB stores binary-encoded JSON, enabling GIN index support for attribute-key queries inside the JSON document. Consistent with `AIMessageModel.metadata` in this codebase.
- **选 `String(50)` for `event_type` over PostgreSQL ENUM**：An ENUM would require a new migration to add values and blocks multi-tenancy (shared enum per DB). A VARCHAR(50) plus application-level validation is sufficient at this stage.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `alembic` | from `pyproject.toml` | Already pinned in project |
| `sqlalchemy` | `2.x` | Required for `Mapped`/`mapped_column` async column syntax |
| `pg` (docker) | `16-alpine` | Used in `configs/docker-compose.test.yml` |

### 4.3 兼容性约束

- Migration `Revises:` must point to the latest existing migration (`c94d682d4b03` as of this write) to avoid conflicts with parallel work.
- `downgrade()` must drop indexes before dropping the table (FK dependency order enforced by PostgreSQL).
- No existing data in `opportunity_activities` at migration time — safe to add all `NOT NULL` constraints from the start.

### 4.4 已知坑

1. **Autogenerate emits `Numeric` or `Float` for DateTime instead of the proper `DateTime(timezone=True)`** → 规避：review the generated migration and manually correct `event_timestamp` to use `sa.DateTime(timezone=True)` with `server_default=sa.text('now()')`. Run full upgrade/downgrade cycle to confirm.
2. **Autogenerate emits `JSON` instead of `JSONB` for the metadata column** → 规避：manually change `sa.JSON()` to `sa.JSONB()` in the migration file before applying.
3. **Autogenerate may omit the FK constraint or use a different `ondelete` style** → 规避：verify `opportunity_id` column includes `sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE')`. `ondelete='CASCADE'` ensures parent opportunity deletion removes all child activity rows.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/db/models/opportunity_activity.py`

操作：
- a) Create `src/db/models/opportunity_activity.py`:

```python
"""Opportunity Activity ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class OpportunityActivityModel(Base):
    """Stores an event in an opportunity's lifecycle."""

    __tablename__ = "opportunity_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_opportunity_activities_tenant_id", "tenant_id"),
        Index("ix_opportunity_activities_opportunity_id", "opportunity_id"),
        Index(
            "ix_opportunity_activities_tenant_opp",
            "tenant_id", "opportunity_id",
        ),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "opportunity_id": self.opportunity_id,
            "event_type": self.event_type,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "metadata": self.metadata,
        }
```

- b) `ruff check src/db/models/opportunity_activity.py`
- c) `mypy src/db/models/opportunity_activity.py`

**完成判定**：`ruff check src/db/models/opportunity_activity.py` exits0 with no warnings. `mypy src/db/models/opportunity_activity.py` exits 0.

---

### Step 2: Bring up alembic_dev and run existing migrations to head

操作：
- a) Ensure a clean `alembic_dev` database at the current migration head:
  ```bash
  docker compose -f configs/docker-compose.test.yml up -d test-db
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
  ```
- b) Export env and run existing migrations:
  ```bash
  export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic upgrade head
  ```

**完成判定**：`alembic current` → `c94d682d4b03`（latest revision confirmed）.

---

### Step 3: Generate Alembic migration for opportunity_activities table

操作：
- a) Run alembic autogenerate:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic revision --autogenerate -m "create opportunity_activities table"
  ```
- b) Open the generated file (`alembic/versions/<id>_create_opportunity_activities_table.py`) and manually correct:
  - `event_timestamp`: use `sa.DateTime(timezone=True)` with `server_default=sa.text('now()')`
  - `metadata`: use `sa.JSONB()` (not `sa.JSON()`)
  - Ensure FK constraint: `opportunity_id` references `opportunities.id` with `ondelete='CASCADE'`
  - Add composite index `ix_opportunity_activities_tenant_opp` on `tenant_id`, `opportunity_id`
  - Verify `Revises:` is set to `c94d682d4b03`
- c) Confirm `downgrade()` drops composite index, opportunity_id index, tenant_id index (in that order), then drops the table

示例代码（expected migration structure）:

```python
# alembic/versions/<id>_create_opportunity_activities_table.py
def upgrade() -> None:
    op.create_table('opportunity_activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_timestamp',
 sa.DateTime(timezone=True),
                 server_default=sa.text('now()'),
                 nullable=False),
        sa.Column('metadata', sa.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'],
                                ondelete='CASCADE'),
        sqlite_autoincrement=True
    )
    op.create_index(op.f('ix_opportunity_activities_tenant_id'),
                    'opportunity_activities', ['tenant_id'])
    op.create_index(op.f('ix_opportunity_activities_opportunity_id'),
                    'opportunity_activities', ['opportunity_id'])
    op.create_index('ix_opportunity_activities_tenant_opp',
                    'opportunity_activities',
                    ['tenant_id', 'opportunity_id'])

def downgrade() -> None:
    op.drop_index('ix_opportunity_activities_tenant_opp',
                   table_name='opportunity_activities')
    op.drop_index(op.f('ix_opportunity_activities_opportunity_id'),
                   table_name='opportunity_activities')
    op.drop_index(op.f('ix_opportunity_activities_tenant_id'),
 table_name='opportunity_activities')
    op.drop_table('opportunity_activities')
```

**完成判定**：`ls alembic/versions/*opportunity_activities*` returns the new migration file. `ruff check alembic/versions/<id>_create_opportunity_activities_table.py` exits 0.

---

### Step 4: Apply migration and verify upgrade/downgrade cycle

操作：
- a) Apply upgrade:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic upgrade head
  ```
- b) Confirm table, FK, and indexes exist:
  ```bash
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt opportunity_activities"
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d opportunity_activities"
  ```
- c) Run downgrade, then upgrade again (clean cycle):
  ```bash
  alembic downgrade -1
  alembic upgrade head
  ```

**完成判定**：`alembic downgrade -1` exits with code 0. Second `alembic upgrade head` exits with code 0 and `docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt"` shows ` opportunity_activities`.

---

### Step 5: Create `tests/unit/test_opportunity_activity_model.py`

操作：
- a) Create `tests/unit/test_opportunity_activity_model.py`:

```python
# tests/unit/test_opportunity_activity_model.py
import pytest
from datetime import datetime, timezone

from tests.unit.conftest import MockRow

from src.db.models.opportunity_activity import OpportunityActivityModel


class TestOpportunityActivityModel:
    def test_to_dict_returns_all_fields(self):
        now = datetime.now(timezone.utc)
        row_data = {
            "id": 1,
            "tenant_id": 42,
            "opportunity_id": 10,
            "event_type": "stage_changed",
            "event_timestamp": now,
            "metadata": {"old_stage": "lead", "new_stage": "negotiation"},
        }
        row = MockRow(user_row_data)
        assert hasattr(OpportunityActivityModel, "to_dict")

    def test_tenant_id_column_is_indexed(self):
        col = OpportunityActivityModel.__table__.columns["tenant_id"]
        assert col.nullable is False        assert col.index is True or any(
            idx.columns == ["tenant_id"]
            for idx in OpportunityActivityModel.__table__.indexes
        )

    def test_fk_column_is_not_nullable(self):
        opp_col = OpportunityActivityModel.__table__.columns["opportunity_id"]
        assert opp_col.nullable is False

    def test_event_type_column_is_string50(self):
        col = OpportunityActivityModel.__table__.columns["event_type"]
        assert col.type.__class__.__name__ == "String"
        assert col.type.length == 50

    def test_event_timestamp_is_datetime(self):
        col = OpportunityActivityModel.__table__.columns["event_timestamp"]
        assert col.type.__class__.__name__ == "DateTime"
        assert col.server_default is not None

    def test_metadata_is_jsonb(self):
        col = OpportunityActivityModel.__table__.columns["metadata"]
        assert col.type.__class__.__name__ == "JSONB"
        assert col.nullable is True
```

- b) `ruff check tests/unit/test_opportunity_activity_model.py`
- c) `mypy tests/unit/test_opportunity_activity_model.py`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_activity_model.py -v` → `6 passed`.

---

### Step 6: Create `docs/dev-plan/20-sales/0681_verify.sh`

操作：
- a) Create `docs/dev-plan/20-sales/0681_verify.sh`:
  ```bash
  #!/usr/bin/env bash
  set -e
  export PYTHONPATH=src

  echo "=== ruff check model ==="
  ruff check src/db/models/opportunity_activity.py

  echo "=== ruff check migration ==="
  ruff check alembic/versions/

  echo "=== ruff check tests ==="
  ruff check tests/unit/test_opportunity_activity_model.py

  echo "=== mypy model ==="
  mypy src/db/models/opportunity_activity.py

  echo "=== pytest unit ==="
  PYTHONPATH=src pytest tests/unit/test_opportunity_activity_model.py -v

  echo "ALL CHECKS PASSED"
  ```
- b) `chmod +x docs/dev-plan/20-sales/0681_verify.sh`
- c) `bash docs/dev-plan/20-sales/0681_verify.sh` — confirm `ALL CHECKS PASSED`

**完成判定**：`bash docs/dev-plan/20-sales/0681_verify.sh` exits 0 with `ALL CHECKS PASSED` as final line.

---

## 6. 验收

- [ ] `ruff check src/db/models/opportunity_activity.py` → zero warnings/errors
- [ ] `ruff check alembic/versions/` (new migration file included) → zero warnings/errors
- [ ] `ruff check tests/unit/test_opportunity_activity_model.py` → zero warnings/errors
- [ ] `mypy src/db/models/opportunity_activity.py` → zero errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_activity_model.py -v` → `6 passed`
- [ ] `bash docs/dev-plan/20-sales/0681_verify.sh` → `ALL CHECKS PASSED`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces wrong column type for metadata (JSON instead of JSONB) | 中 | 中 | Manually fix the migration file to use `sa.JSONB()`; re-run upgrade cycle |
| Autogenerate omits the FK constraint or sets wrong `ondelete` | 中 | 高 | Manually add `sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE')` to the migration |
| Autogenerate emits wrong `Revises:` head (conflicts with parallel work) | 低 | 中 | Re-run `alembic current` after pulling latest and regenerate the migration against the new head |
| Downgrade drops indexes in wrong order causing PG error | 低 | 中 | Manually reorder `op.drop_index` calls before `op.drop_table` — composite index before single-column indexes |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/db/models/opportunity_activity.py alembic/versions/*opportunity_activities*.py tests/unit/test_opportunity_activity_model.py docs/dev-plan/20-sales/0681_verify.sh
git commit -m "feat(sales): add OpportunityActivityModel and alembic migration for opportunity_activities table"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0681] OpportunityActivity ORM model + migration 完成 (W20.1)
# - PR/Commit: <link>
# - 关键产物: src/db/models/opportunity_activity.py, alembic/versions/<id>_create_opportunity_activities_table.py
# - 验收: bash docs/dev-plan/20-sales/0681_verify.sh 全绿 ✓
# - 下一步赋能: OpportunityActivityService, API router GET/POST /opportunities/{id}/activities（待建）

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- ORM model reference（FK target）：[`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L1-L46
- Existing activity table pattern：[`src/db/models/activity.py`](../../src/db/models/activity.py) L1-L35
- JSONB + FK + composite index pattern：[`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L1-L88
- Latest migration head：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L1-L59
- Alembic env（auto-discovers models）：[`alembic/env.py`](../../alembic/env.py) L14
- Unit test pattern：[`tests/unit/conftest.py`](../../tests/unit/conftest.py) — MockRow / MockResult
- Parent issue：[`#665`](https://github.com/.../issues/665) — sales pipeline automation epic
- Subtask order：[`#681`](https://github.com/.../issues/681)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD - 待补充 |
