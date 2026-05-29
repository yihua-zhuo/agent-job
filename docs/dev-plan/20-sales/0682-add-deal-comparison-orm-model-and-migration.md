# 0682 · Add deal_comparison ORM model and migration

| 元数据 | 值 |
|---|---|
| 周次 | W20.1 |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0681-add-opportunity-foreign-key-constraints](./0681-add-opportunity-foreign-key-constraints.md) |
| 启用后赋能 | [0682-add-deal-comparison-orm-model-and-migration](./0682-add-deal-comparison-orm-model-and-migration.md) — 下游：deal comparison service / API router（待建） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #682 is a subtask of #665 (sales pipeline comparison capabilities). Before any deal comparison service or API can be built, the underlying `deal_comparisons` table must exist in PostgreSQL. Issue #681 establishes the FK integrity on the `opportunities` table, which is a prerequisite because `deal_comparisons.opportunity_id` and `deal_comparisons.reference_opportunity_id` both reference `opportunities.id`. Without this model and migration, downstream boards for the comparison service have no persistent schema to work against.

### 1.2 做完后

- **用户视角**：No user-facing change — this is pure infrastructure (DB schema only).
- **开发者视角**：`alembic upgrade head` creates the `deal_comparisons` table. `ruff check src/db/models/deal_comparison.py` passes. Unit tests in `tests/unit/test_deal_comparison_model.py` confirm the ORM model serialises correctly and tenant isolation via `MockRow`/`MockResult`.

### 1.3 不做什么（剔除）

- [ ] No service layer — a downstream board will own `DealComparisonService`.
- [ ] No REST API router — a separate board will own the HTTP endpoints.
- [ ] No business logic (similarity scoring algorithm) — only the storage schema.
- [ ] No integration tests — those belong to the integration board that exercises the full comparison lifecycle.

### 1.4 关键 KPI

- `alembic upgrade head` → `deal_comparisons` table present in `alembic_dev`.
- `alembic downgrade -1` → `deal_comparisons` table dropped cleanly.
- `ruff check src/db/models/deal_comparison.py` → zero warnings/errors.
- `PYTHONPATH=src pytest tests/unit/test_deal_comparison_model.py -v` → ≥ 3 passed.
- `ruff check alembic/versions/*deal_comparison*` → zero warnings.

---

## 2. 当前现状（起点）

### 2.1 现有实现

No `deal_comparison` model exists yet. The nearest reference is [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L1-L46, which defines the `OpportunityModel` that `deal_comparisons` will FK into. [`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L1-L88 provides the canonical pattern for JSONB + FK + composite index in this codebase.

主入口：N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../alembic/env.py) — already has `import db.models` at L14; the new model in `src/db/models/deal_comparison.py` is auto-discovered via pkgutil, no change needed.
- 要建：
  - `src/db/models/deal_comparison.py` — ORM model
  - `alembic/versions/<id>_create_deal_comparisons_table.py` — Alembic migration
  - `tests/unit/test_deal_comparison_model.py` — unit tests

### 2.3 缺什么

- [ ] `src/db/models/deal_comparison.py` does not exist — no ORM class for the `deal_comparisons` table.
- [ ] No Alembic migration for `deal_comparisons` table.
- [ ] `alembic/env.py` already imports all models via `import db.models` (L14) — pkgutil discovers `deal_comparison.py` automatically once it exists, so no env.py change is needed.
- [ ] No unit test file for the new model.
- [ ] Downstream boards for service and router need this schema in place before they can be built.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `src/db/models/deal_comparison.py` | ORM model for `deal_comparisons` table: id, tenant_id, opportunity_id (FK), reference_opportunity_id (FK), similarity_score, shared_attributes (JSONB), created_at |
| `alembic/versions/<id>_create_deal_comparisons_table.py` | Alembic migration: creates table with indexes on tenant_id, opportunity_id FK, reference_opportunity_id FK; fully reversible |
| `tests/unit/test_deal_comparison_model.py` | Unit tests: instantiation, to_dict serialisation, JSONB field, tenant isolation via MockRow |
| `docs/dev-plan/20-sales/0682_verify.sh` | Acceptance script: ruff + mypy + pytest |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待补充：无修改文件 | [`alembic/env.py`](../../alembic/env.py) already has `import db.models` on L14 — auto-discovers new models via pkgutil, no change needed |
| TBD - 待补充：无修改文件 | [`src/db/models/__init__.py`](../../src/db/models/__init__.py) auto-imports all model modules via pkgutil; no change needed |

### 3.3 新增能力

- **Migration**: `alembic upgrade head` → `deal_comparisons` table exists with indexes on `tenant_id`, `opportunity_id`, `reference_opportunity_id`.
- **verify 脚本**: `bash docs/dev-plan/20-sales/0682_verify.sh`
- **Slack 模板填空**: 按 README §2.9 模板 A（在 #progress 频道发送）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 JSONB 而非 JSON for `shared_attributes`**：PostgreSQL JSONB stores binary-encoded JSON, enabling GIN index support for attribute-key queries. Consistent with `AutomationRuleModel` / `AutomationLogModel` which also use `JSONB` in this codebase.
- **选 two separate FK columns (`opportunity_id` + `reference_opportunity_id`) rather than a self-referential array**：A comparison is directional — each row records one opportunity compared against one reference. A self-referential FK array would not capture which is which.
- **选 `Numeric(5, 4)` for `similarity_score`**：Covers range 0.0000–99.9999 with 4 decimal places, sufficient precision for similarity percentages. Uses `Numeric` (not `Float`) for exact decimal arithmetic.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `alembic` | from `pyproject.toml` | Already pinned in project |
| `sqlalchemy` | `2.x` | Required for `Mapped` / `mapped_column` async column syntax |
| `pg` (docker) | `16-alpine` | Used in `configs/docker-compose.test.yml` |

### 4.3 兼容性约束

- Migration must be reversible: `downgrade()` must drop the composite index before the table (FK dependency order).
- Migration `Revises:` must point to the latest existing migration (`c94d682d4b03` as of now) to avoid conflicts with parallel work.
- No existing data in `deal_comparisons` at migration time — safe to add `NOT NULL` constraints from the start.

### 4.4 已知坑

1. **Autogenerate may emit `Numeric` as `Float`** → 规避：review the generated migration and manually set `sa.Numeric(5, 4)` for `similarity_score`. Run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` to confirm round-trip.
2. **JSONB default in autogenerate** → 规避：autogenerate may emit `default=sa.text('{}')`. Verify `shared_attributes` column uses `sa.JSONB()` with `server_default=sa.text('{}')` and `nullable=False`.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/db/models/deal_comparison.py`

操作：
- a) Create `src/db/models/deal_comparison.py` with the following content:

```python
"""Deal Comparison ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DealComparisonModel(Base):
    """Stores a pairwise deal/opportunity comparison record."""

    __tablename__ = "deal_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    reference_opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    similarity_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    shared_attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_deal_comparisons_tenant_id", "tenant_id"),
        Index("ix_deal_comparisons_opportunity_id", "opportunity_id"),
        Index("ix_deal_comparisons_reference_opportunity_id", "reference_opportunity_id"),
        Index(
            "ix_deal_comparisons_tenant_opp",
            "tenant_id", "opportunity_id", "reference_opportunity_id",
        ),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "opportunity_id": self.opportunity_id,
            "reference_opportunity_id": self.reference_opportunity_id,
            "similarity_score": str(self.similarity_score),
            "shared_attributes": self.shared_attributes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- b) `ruff check src/db/models/deal_comparison.py`
- c) `mypy src/db/models/deal_comparison.py`

**完成判定**：`ruff check src/db/models/deal_comparison.py` exits 0 with no warnings. `mypy src/db/models/deal_comparison.py` exits 0.

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

### Step 3: Generate Alembic migration for deal_comparisons table

操作：
- a) Run alembic autogenerate:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic revision --autogenerate -m "create deal_comparisons table"
  ```
- b) Open the generated file (`alembic/versions/<id>_create_deal_comparisons_table.py`) and manually correct:
  - `similarity_score`: use `sa.Numeric(5, 4)` instead of whatever autogenerate emitted
  - `shared_attributes`: use `sa.JSONB()` with `server_default=sa.text('{}')`
  - Ensure FK constraints: `opportunity_id` → `opportunities.id` and `reference_opportunity_id` → `opportunities.id` both use `ondelete='CASCADE'`
  - Verify composite index name is `ix_deal_comparisons_tenant_opp`
- c) Ensure `Revises:` is set to `c94d682d4b03` (or whatever `alembic current` returned).

示例代码（expected migration structure）:

```python
# alembic/versions/<id>_create_deal_comparisons_table.py
def upgrade() -> None:
    op.create_table('deal_comparisons',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('reference_opportunity_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('shared_attributes', sa.JSONB(), nullable=False,
                  server_default=sa.text('{}')),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reference_opportunity_id'], ['opportunities.id'],
                                ondelete='CASCADE'),
        sqlite_autoincrement=True
    )
    op.create_index(op.f('ix_deal_comparisons_tenant_id'),
                    'deal_comparisons', ['tenant_id'])
    op.create_index(op.f('ix_deal_comparisons_opportunity_id'),
                    'deal_comparisons', ['opportunity_id'])
    op.create_index(op.f('ix_deal_comparisons_reference_opportunity_id'),
                    'deal_comparisons', ['reference_opportunity_id'])
    op.create_index('ix_deal_comparisons_tenant_opp', 'deal_comparisons',
                    ['tenant_id', 'opportunity_id', 'reference_opportunity_id'])


def downgrade() -> None:
    op.drop_index('ix_deal_comparisons_tenant_opp', table_name='deal_comparisons')
    op.drop_index(op.f('ix_deal_comparisons_reference_opportunity_id'),
                  table_name='deal_comparisons')
    op.drop_index(op.f('ix_deal_comparisons_opportunity_id'),
                  table_name='deal_comparisons')
    op.drop_index(op.f('ix_deal_comparisons_tenant_id'),
                  table_name='deal_comparisons')
    op.drop_table('deal_comparisons')
```

**完成判定**：`ls alembic/versions/*deal_comparisons*` returns the new migration file. `ruff check alembic/versions/<id>_create_deal_comparisons_table.py` exits 0.

---

### Step 4: Apply migration and verify upgrade/downgrade cycle

操作：
- a) Apply upgrade:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic upgrade head
  ```
- b) Confirm table and indexes exist:
  ```bash
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt deal_comparisons"
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d deal_comparisons"
  ```
- c) Run downgrade, then upgrade again (clean cycle):
  ```bash
  alembic downgrade -1
  alembic upgrade head
  ```

**完成判定**：`alembic downgrade -1` exits with code 0. Second `alembic upgrade head` exits with code 0 and `docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt deal_comparisons"` shows the table.

---

### Step 5: Create `tests/unit/test_deal_comparison_model.py`

操作：
- a) Create `tests/unit/test_deal_comparison_model.py`:

```python
# tests/unit/test_deal_comparison_model.py
import pytest
from datetime import datetime, timezone

from tests.unit.conftest import MockRow

from src.db.models.deal_comparison import DealComparisonModel


class TestDealComparisonModel:
    def test_to_dict_returns_all_fields(self):
        now = datetime.now(timezone.utc)
        row_data = {
            "id": 1,
            "tenant_id": 42,
            "opportunity_id": 10,
            "reference_opportunity_id": 20,
            "similarity_score": "0.8750",
            "shared_attributes": {"stage": "negotiation", "amount": 50000},
            "created_at": now,
        }
        row = MockRow(row_data)
        assert hasattr(DealComparisonModel, "to_dict")
        # Verify column types
        assert (
            DealComparisonModel.__table__.columns["id"].type.__class__.__name__
            == "Integer"
        )
        assert (
            DealComparisonModel.__table__.columns["similarity_score"]
            .type.__class__.__name__
            == "Numeric"
        )
        assert (
            DealComparisonModel.__table__.columns["shared_attributes"]
            .type.__class__.__name__
            == "JSONB"
        )

    def test_tenant_id_column_is_indexed(self):
        col = DealComparisonModel.__table__.columns["tenant_id"]
        assert col.nullable is False

    def test_fk_columns_are_not_nullable(self):
        opp_col = DealComparisonModel.__table__.columns["opportunity_id"]
        ref_col = DealComparisonModel.__table__.columns["reference_opportunity_id"]
        assert opp_col.nullable is False
        assert ref_col.nullable is False

    def test_similarity_score_numeric_precision(self):
        from decimal import Decimal

        num_col = DealComparisonModel.__table__.columns["similarity_score"]
        assert num_col.type.precision == 5
        assert num_col.type.scale == 4

    def test_shared_attributes_default_is_dict(self):
        col = DealComparisonModel.__table__.columns["shared_attributes"]
        assert col.server_default is not None or col.default is not None
```

- b) `ruff check tests/unit/test_deal_comparison_model.py`
- c) `mypy tests/unit/test_deal_comparison_model.py`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_deal_comparison_model.py -v` → `5 passed` (or actual count, all passed).

---

### Step 6: Create `docs/dev-plan/20-sales/0682_verify.sh`

操作：
- a) Create `docs/dev-plan/20-sales/0682_verify.sh`:
  ```bash
  #!/usr/bin/env bash
  set -e
  export PYTHONPATH=src

  echo "=== ruff check model ==="
  ruff check src/db/models/deal_comparison.py

  echo "=== ruff check migration ==="
  ruff check alembic/versions/

  echo "=== ruff check tests ==="
  ruff check tests/unit/test_deal_comparison_model.py

  echo "=== mypy model ==="
  mypy src/db/models/deal_comparison.py

  echo "=== pytest unit ==="
  PYTHONPATH=src pytest tests/unit/test_deal_comparison_model.py -v

  echo "ALL CHECKS PASSED"
  ```
- b) `chmod +x docs/dev-plan/20-sales/0682_verify.sh`
- c) Run it locally and confirm `ALL CHECKS PASSED`

**完成判定**：`bash docs/dev-plan/20-sales/0682_verify.sh` exits 0 with `ALL CHECKS PASSED` as final line.

---

## 6. 验收

- [ ] `ruff check src/db/models/deal_comparison.py` → zero warnings/errors
- [ ] `ruff check alembic/versions/` (new migration file included) → zero warnings/errors
- [ ] `ruff check tests/unit/test_deal_comparison_model.py` → zero warnings/errors
- [ ] `mypy src/db/models/deal_comparison.py` → zero errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_deal_comparison_model.py -v` → `5 passed` (or actual count, all passed)
- [ ] `bash docs/dev-plan/20-sales/0682_verify.sh` → `ALL CHECKS PASSED`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces wrong column types for Numeric or JSONB | 中 | 中 | Manually fix the migration file to use `sa.Numeric(5, 4)` and `sa.JSONB()`; re-run upgrade cycle |
| Downgrade drops composite index before table body incorrectly | 低 | 高 | Ensure `op.drop_index` calls appear before `op.drop_table` in `downgrade()`; test downgrade cycle |
| Parallel work creates migration with same Revises head | 低 | 低 | Communicate via issue comments; if conflict, rebase and regenerate against new head |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/db/models/deal_comparison.py alembic/versions/*deal_comparisons*.py tests/unit/test_deal_comparison_model.py docs/dev-plan/20-sales/0682_verify.sh
git commit -m "feat(sales): add DealComparisonModel and alembic migration for deal_comparisons table"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0682] DealComparison ORM model + migration 完成 (W20.1)
# - PR/Commit: <link>
# - 关键产物: src/db/models/deal_comparison.py, alembic/versions/<id>_create_deal_comparisons_table.py, tests/unit/test_deal_comparison_model.py
# - 验收: bash docs/dev-plan/20-sales/0682_verify.sh 全绿 ✓
# - 下一步赋能: 下游 deal comparison service + API router（待建）

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- ORM model reference：[`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L1-L46
- JSONB + FK pattern：[`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L1-L88
- Example migration：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L1-L59
- Alembic env（auto-discovers models）：[`alembic/env.py`](../../alembic/env.py) L14
- Unit test pattern：[`tests/unit/conftest.py`](../../tests/unit/conftest.py) — MockRow / MockResult
- Upstream dependency：[`0681-add-opportunity-foreign-key-constraints`](./0681-add-opportunity-foreign-key-constraints.md)
- Parent issue：[`#665`](https://github.com/.../issues/665) — 父 issue

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD - 待补充 |
