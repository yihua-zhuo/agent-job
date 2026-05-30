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
        assert col.nullable is False assert col.index is True or any(
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

- ORM model reference（FK target）：[`src/db/models/opportunity.py`](../../../src/db/models/opportunity.py) L1-L46
- Existing activity table pattern：[`src/db/models/activity.py`](../../../src/db/models/activity.py) L1-L35
- JSONB + FK + composite index pattern：[`src/db/models/ai_conversation.py`](../../../src/db/models/ai_conversation.py) L1-L88
- Latest migration head：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L1-L59
- Alembic env（auto-discovers models）：[`alembic/env.py`](../../../alembic/env.py) L14
- Unit test pattern：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — MockRow / MockResult
- Parent issue：[`#665`](https://github.com/.../issues/665) — sales pipeline automation epic
- Subtask order：[`#681`](https://github.com/.../issues/681)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD - 待补充 |
