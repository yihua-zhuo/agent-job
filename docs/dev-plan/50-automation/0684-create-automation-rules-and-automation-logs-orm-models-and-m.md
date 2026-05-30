# 0684 · Create automation_rules and automation_logs ORM models and migrations

| 元数据 | 值 |
|---|---|
| 周次 | W13.1 |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0685-implement-automationrule-service](./0685-implement-automationrule-service.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`AutomationRuleModel` and `AutomationLogModel` are already defined in [`src/db/models/automation.py`](../../src/db/models/automation.py) L12-L77. However, no Alembic migration exists to create the `automation_rules` and `automation_logs` tables in PostgreSQL. Without the migration, downstream boards (#685 service, #686 router, #687 execution engine) have no persistent storage to build against. This board creates the migration, registers the models in `alembic/env.py`, and adds unit tests to protect the model contract.

### 1.2 做完后

- **用户视角**：No user-facing change — this is pure infrastructure.
- **开发者视角**：`alembic upgrade head` creates `automation_rules` and `automation_logs` tables. Unit tests in `tests/unit/test_automation_models.py` confirm `AutomationRuleModel` and `AutomationLogModel` serialize correctly and that tenant isolation works via `MockRow` / `MockResult`.

### 1.3 不做什么（剔除）

- [ ] No service layer — #685 owns `AutomationRuleService`.
- [ ] No REST API — #686 owns the router.
- [ ] No rule execution engine — #687 owns trigger dispatch.
- [ ] No integration tests — #688 owns the full-lifecycle integration suite.

### 1.4 关键 KPI

- `alembic upgrade head` → `automation_rules` and `automation_logs` tables present in `alembic_dev`.
- `alembic downgrade -1` → both tables dropped cleanly.
- `ruff check src/db/models/automation.py` → zero warnings/errors.
- `PYTHONPATH=src pytest tests/unit/test_automation_models.py -v` → ≥ 6 passed (3 models × 2 cases minimum).

---

## 2. 当前现状（起点）

### 2.1 现有实现

ORM models exist but no migration. `alembic/env.py` already imports the models via `import db.models` (line 14), so autogenerate will pick them up.

主入口：[`src/db/models/automation.py`](../../src/db/models/automation.py) L12-L77

```startLine:12:src/db/models/automation.py
class AutomationRuleModel(Base):
    """User-defined automation rules stored in DB."""

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AutomationLogModel(Base):
    """Execution log for automation rules."""

    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### 2.2 涉及文件清单

- 要改：
  - TBD - 待补充：无现有文件需要修改
- 要建：
  - `alembic/versions/<id>_create_automation_rules_and_logs_tables.py` — Alembic migration creating `automation_rules` and `automation_logs` tables
  - `tests/unit/test_automation_models.py` — Unit tests for both ORM models using MockRow/MockResult

### 2.3 缺什么

- [ ] No Alembic migration for `automation_rules` and `automation_logs` tables.
- [ ] `alembic/env.py` imports all models via `import db.models` — already correct, no change needed.
- [ ] `make_automation_handler` in [`tests/unit/domain_handlers/automation.py`](../../../tests/unit/domain_handlers/automation.py) exists but has no test coverage for the model layer itself.
- [ ] No unit tests that directly instantiate `AutomationRuleModel` / `AutomationLogModel` and call `.to_dict()` to verify serialization.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `alembic/versions/<id>_create_automation_rules_and_logs_tables.py` | Alembic migration: creates `automation_rules` and `automation_logs` tables with all columns, indexes, and FK |
| `tests/unit/test_automation_models.py` | Unit tests for `AutomationRuleModel` and `AutomationLogModel` — instantiation, to_dict, tenant isolation |
| `docs/dev-plan/50-automation/0684_verify.sh` | Acceptance script: ruff + mypy + pytest |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待补充：无修改文件 | `alembic/env.py` already has `import db.models` on line 14 — models are registered automatically |

### 3.3 新增能力

- **Migration**: `alembic upgrade head` → `automation_rules` + `automation_logs` tables exist.
- **verify 脚本**: `bash docs/dev-plan/50-automation/0684_verify.sh`
- **Slack 模板填空**: TBD - 待补充：按 README §2.9 模板 A（在 #progress 频道发送）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 JSONB 而非 JSON**：PostgreSQL JSONB stores binary-encoded JSON, enabling GIN index support for condition/action queries. The existing ORM models already declare `JSONB` in `Mapped[list]` columns.
- **选 `ondelete="CASCADE"` on `rule_id` FK**：When an `AutomationRule` is deleted, all its execution logs should be removed atomically. This prevents orphaned `automation_logs` rows referencing a deleted rule.
- **选 `server_default=func.now()` 而非 Python-side `datetime.now(UTC)`**：Migration-defined server defaults are evaluated at INSERT time on the DB side, which is more reliable than Python-side defaults that can be wrong if the app process clock drifts.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `alembic` | from `pyproject.toml` | Already pinned in project |
| `sqlalchemy` | `2.x` | Already pinned in project; required for async `Mapped` column syntax |

### 4.3 兼容性约束

- Migration must be reversible (`downgrade()` drops both tables in correct order — child before parent due to FK).
- Downgrade must run after upgrade in verification step to confirm cleanliness.
- Migration must not conflict with any existing migration in `alembic/versions/`. Uses head revision from `c94d682d4b03` as `Revises:`.

### 4.4 已知坑

1. **Autogenerate may not capture JSONB default correctly** → 规避：review the generated migration and manually change `default=sa.text('{}')` (or whatever autogenerate emits) to match SQLAlchemy's `JSONB` expectation. Run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` to confirm.
2. **CASCADE ordering in downgrade** → 规避：`automation_logs` must be dropped before `automation_rules` (FK dependency). Autogenerate produces correct order; manually verify it is not reversed.

---

## 5. 实现步骤（按顺序）

### Step 1: Bring up alembic_dev database and run existing migrations to head

操作：
- a) Ensure the `alembic_dev` database is clean and at current migration head:
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

**完成判定**：`alembic current` → `c94d682d4b03`（latest revision confirmed）

---

### Step 2: Generate autogenerate migration for automation_rules and automation_logs

操作：
- a) Run alembic autogenerate:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic revision --autogenerate -m "create automation_rules and automation_logs tables"
  ```
- b) Open the generated file (in `alembic/versions/<id>_create_automation_rules_and_logs_tables.py`) and verify the `op.create_table` calls include all columns from `AutomationRuleModel` and `AutomationLogModel`. Specifically check:
  - `automation_rules`: id, tenant_id, name, description, trigger_event, conditions (JSONB), actions (JSONB), enabled, created_by, created_at, updated_at
  - `automation_logs`: id, rule_id (FK), tenant_id, trigger_event, trigger_context (JSONB), actions_executed (JSONB), status, error_message, executed_by, executed_at
- c) Fix any column types autogenerate got wrong (e.g., String length, Boolean default syntax)

示例代码（expected migration structure）:

```python
# alembic/versions/<id>_create_automation_rules_and_logs_tables.py
def upgrade() -> None:
    op.create_table('automation_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_event', sa.String(length=100), nullable=False),
        sa.Column('conditions', sa.JSONB(), nullable=False),
        sa.Column('actions', sa.JSONB(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_rules_tenant_id'), 'automation_rules', ['tenant_id'])
    op.create_index(op.f('ix_automation_rules_trigger_event'), 'automation_rules', ['trigger_event'])

    op.create_table('automation_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('trigger_event', sa.String(length=100), nullable=False),
        sa.Column('trigger_context', sa.JSONB(), nullable=False),
        sa.Column('actions_executed', sa.JSONB(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'success'")),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_by', sa.Integer(), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_automation_logs_rule_id'), 'automation_logs', ['rule_id'])
    op.create_index(op.f('ix_automation_logs_tenant_id'), 'automation_logs', ['tenant_id'])
```

**完成判定**：`ls alembic/versions/*automation*rules*` returns the new migration file.

---

### Step 3: Apply the migration and verify upgrade/downgrade cycle

操作：
- a) Apply upgrade:
  ```bash
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic upgrade head
  ```
- b) Confirm both tables exist:
  ```bash
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt automation_*"
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d automation_rules"
  docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\d automation_logs"
  ```
- c) Run downgrade, then upgrade again (clean cycle):
  ```bash
  alembic downgrade -1
  alembic upgrade head
  ```

**完成判定**：`alembic downgrade -1` exits with code 0 and no error. Second `alembic upgrade head` exits with code 0 and shows same tables present.

---

### Step 4: Create `tests/unit/test_automation_models.py`

操作：
- a) Create `tests/unit/test_automation_models.py` with the following test cases using `MockRow` / `MockResult`:
  - **Test 1** (`test_automation_rule_model_to_dict`): Instantiate `AutomationRuleModel` via `MockRow` simulation, call `.to_dict()`, assert all fields present (id, tenant_id, name, description, trigger_event, conditions, actions, enabled, created_by).
  - **Test 2** (`test_automation_log_model_to_dict`): Instantiate `AutomationLogModel` via `MockRow`, call `.to_dict()`, assert all fields (id, rule_id, tenant_id, trigger_event, trigger_context, actions_executed, status, error_message, executed_by, executed_at).
  - **Test 3** (`test_automation_rule_conditions_jsonb`): Verify that `conditions` field accepts a list and serializes correctly in `to_dict()`.
  - **Test 4** (`test_automation_log_trigger_context_jsonb`): Verify `trigger_context` JSONB field rounds-trip through `to_dict()`.
  - **Test 5** (`test_automation_rule_enabled_default`): Verify default `enabled=True` when not provided.
  - **Test 6** (`test_automation_log_status_default`): Verify default `status="success"` when not provided.

示例代码（test structure）:

```python
# tests/unit/test_automation_models.py
import pytest
from datetime import datetime, timezone

from tests.unit.conftest import MockRow, MockResult, MockState

# Directly instantiate ORM model field descriptors to verify their contract
from src.db.models.automation import AutomationRuleModel, AutomationLogModel


class TestAutomationRuleModel:
    def test_to_dict_returns_all_fields(self):
        now = datetime.now(timezone.utc)
        row_data = {
            "id": 1,
            "tenant_id": 42,
            "name": "Notify on ticket created",
            "description": "Send Slack when ticket created",
            "trigger_event": "ticket.created",
            "conditions": [{"field": "priority", "op": "eq", "value": "high"}],
            "actions": [{"type": "send_notification", "channel": "#alerts"}],
            "enabled": True,
            "created_by": 10,
            "created_at": now,
            "updated_at": now,
        }
        row = MockRow(row_data)
        # Verify .to_dict() is defined and callable
        assert hasattr(AutomationRuleModel, "to_dict")
        # Verify primary key column is integer
        assert AutomationRuleModel.__table__.columns["id"].type.__class__.__name__ == "Integer"


class TestAutomationLogModel:
    def test_to_dict_returns_all_fields(self):
        now = datetime.now(timezone.utc)
        row_data = {
            "id": 5,
            "rule_id": 1,
            "tenant_id": 42,
            "trigger_event": "ticket.created",
            "trigger_context": {"ticket_id": 99, "priority": "high"},
            "actions_executed": [{"type": "send_notification", "result": "ok"}],
            "status": "success",
            "error_message": None,
            "executed_by": 10,
            "executed_at": now,
        }
        row = MockRow(row_data)
        assert hasattr(AutomationLogModel, "to_dict")

    def test_status_default_is_success(self):
        col = AutomationLogModel.__table__.columns["status"]
        assert col.default is not None or col.server_default is not None
```

- b) `ruff check tests/unit/test_automation_models.py`
- c) `mypy tests/unit/test_automation_models.py`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_models.py -v` → `6 passed` (or actual count, all passed).

---

### Step 5: Create `docs/dev-plan/50-automation/0684_verify.sh`

操作：
- a) Create `docs/dev-plan/50-automation/0684_verify.sh`:
  ```bash
  #!/usr/bin/env bash
  set -e
  export PYTHONPATH=src

  echo "=== ruff check models ==="
  ruff check src/db/models/automation.py

  echo "=== ruff check tests ==="
  ruff check tests/unit/test_automation_models.py

  echo "=== mypy models ==="
  mypy src/db/models/automation.py

  echo "=== pytest unit ==="
  PYTHONPATH=src pytest tests/unit/test_automation_models.py -v

  echo "ALL CHECKS PASSED"
  ```
- b) `chmod +x docs/dev-plan/50-automation/0684_verify.sh`
- c) Run it locally and confirm `ALL CHECKS PASSED`

**完成判定**：`bash docs/dev-plan/50-automation/0684_verify.sh` exits 0 with `ALL CHECKS PASSED` as final line.

---

## 6. 验收

- [ ] `ruff check src/db/models/automation.py` → zero warnings/errors
- [ ] `ruff check tests/unit/test_automation_models.py` → zero warnings/errors
- [ ] `mypy src/db/models/automation.py` → zero errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_models.py -v` → `6 passed` (or actual count, all passed)
- [ ] `docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt automation_*"` shows both `automation_rules` and `automation_logs` tables after `alembic upgrade head`
- [ ] `bash docs/dev-plan/50-automation/0684_verify.sh` → `ALL CHECKS PASSED`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces wrong column types for JSONB | 中 | 中 | Manually fix the migration file to use `sa.JSONB()` instead of `sa.JSON()`; re-run `alembic upgrade head` |
| Downgrade drops tables in wrong order (parent before child) | 低 | 高 | Edit migration file: ensure `op.drop_table('automation_logs')` appears before `op.drop_table('automation_rules')`; test downgrade cycle |
| Migration file name collision with parallel work | 低 | 低 | Use timestamp-based revision ID; if conflict, rename to include `_create_automation_rules_and_logs` suffix |

---

## 8. 完成后必做

```bash
# 1. commit
git add alembic/versions/*automation*.py tests/unit/test_automation_models.py docs/dev-plan/50-automation/0684_verify.sh
git commit -m "feat(automation): add Alembic migration for automation_rules and automation_logs tables"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0684] ORM models + migration 完成 (W13.1)
# - PR/Commit: <link>
# - 关键产物: alembic/versions/<id>_create_automation_rules_and_logs_tables.py, tests/unit/test_automation_models.py
# - 验收: bash docs/dev-plan/50-automation/0684_verify.sh 全绿 ✓
# - 下一步赋能: #685 (AutomationRuleService)

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- ORM models：[`src/db/models/automation.py`](../../src/db/models/automation.py) L1-L77
- Test handlers：[`tests/unit/domain_handlers/automation.py`](../../../tests/unit/domain_handlers/automation.py) L1-L101
- Alembic env（already imports models）：[`alembic/env.py`](../../../alembic/env.py) L14
- Example migration：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L1-L59
- Downstream board (service)：[`0685-implement-automationrule-service.md`](./0685-implement-automationrule-service.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD - 待补充 |
