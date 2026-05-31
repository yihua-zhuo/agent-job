# Workflow Tables Migration · Add Alembic migration for workflow tables with enums and indexes

| 元数据 | 值 |
|---|---|
| Issue | #660 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无（#659 为并行同组，均为 #651 子任务，独立执行） |
| 启用后赋能 | [0685-implement-ruleservice-with-crud-operations](../50-automation/0685-implement-ruleservice-with-crud-operations.md), TBD - 待验证：0687 文件路径待确认 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/db/models/workflow.py` 中定义的 `WorkflowModel` 和 `WorkflowExecutionModel` 当前使用 `String(50)` 存储 `status` 等枚举值，存在数据一致性问题：应用层和 DB 层对合法值的约束分离，无法利用 PostgreSQL enum 类型提供的 compile-time 检查。所有 workflow 相关表（`workflows`, `workflow_executions`）以及计划新增的 `workflow_steps`, `workflow_step_executions` 也缺少 `tenant_id` 复合索引，高并发多租户场景会导致全表扫描。

### 1.2 做完后

- **用户视角**：`无用户可见变化 — 纯底层`
- **开发者视角**：`alembic/versions/<id>_add_workflow_tables.py` 创建 4 张表（`workflows`, `workflow_executions`, `workflow_steps`, `workflow_step_executions`），全部使用 PostgreSQL enum 类型（`step_type`, `step_status`, `workflow_status`）并带 `tenant_id` 和 `instance_id` 索引。Service 层可直接用 ORM 模型，增删改不受应用层约束限制。

### 1.3 不做什么（剔除）

- [ ] CRUD Service 层 — 仅建模和 DB migration，不实现业务逻辑
- [ ] Router 层 — 不暴露 API endpoint
- [ ] 历史数据迁移（现有 String → enum 的数据回填）— 仅新建结构，ALTER 后已有 `String` 值靠应用层兼容处理

### 1.4 关键 KPI

- `ruff check alembic/versions/<new_id>_add_workflow_tables.py` → 0 errors
- `alembic upgrade head` → exit 0
- `alembic downgrade -1` → exit 0
- `alembic upgrade head` → exit 0（三次连续验证通过）
- `alembic revision --autogenerate -m "drift_check"` → 空 migration（无 residual drift）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/db/models/workflow.py`](../../../src/db/models/workflow.py) L{1}-L{76}

```{python}:src/db/models/workflow.py
class WorkflowModel(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkflowExecutionModel(Base):
    __tablename__ = "workflow_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

`workflows` 表在 `b2c3dce4b714_create_all_tables.py` 中已创建，`workflow_executions` 同文件创建但无 `tenant_id` 列。`workflow_steps` 和 `workflow_step_executions` 两张表不存在。

### 2.2 涉及文件清单

- 要改：
  - `alembic/versions/<new_id>_add_workflow_tables.py` — 新建 migration（autogenerate 生成模板，手动补全）
- 要建：
  - `alembic/versions/<new_id>_add_workflow_tables.py` — 创建 4 张 workflow 表 + 3 个 enum 类型 + 索引
  - `tests/unit/test_workflow_model.py` — 3 个测试用例（to_dict 序列化、字段映射、enum 约束）

### 2.3 缺什么

- [ ] `workflow_executions` 表缺少 `tenant_id` 列 — 多租户隔离失效
- [ ] `workflows` / `workflow_executions` 的 `status` 使用 `String(50)`，无 PostgreSQL enum 类型约束
- [ ] 无 `workflow_steps` 表（存储 workflow 内每个 step 的定义）
- [ ] 无 `workflow_step_executions` 表（存储每个 step 的执行记录，含 `instance_id` 索引）
- [ ] 无 `step_type` / `step_status` enum 类型

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_workflow_tables.py` | 创建 4 张 workflow 表 + 3 个 PostgreSQL enum 类型 + 所有索引（含 tenant_id 复合索引、instance_id 索引） |
| `tests/unit/test_workflow_model.py` | 3 个测试用例：to_dict 序列化包含所有字段、字段映射完整性、ORM 模型可正常实例化 |

###_modification（无修改文件，本板块仅新建 migration + 测试）

###_new_capability

- **PostgreSQL enum types**：`step_type`（manual/step/condition/branch/notify）, `step_status`（pending/running/success/failed/skipped）, `workflow_status`（draft/active/paused/completed/cancelled）
- **ORM model**：`WorkflowModel`, `WorkflowExecutionModel` 在 [`src/db/models/workflow.py`](../../../src/db/models/workflow.py)（已存在，本板块不修改模型定义）
- **Migration**：`alembic upgrade head` 创建 `workflow_steps`, `workflow_step_executions` 两张表；ALTER `workflow_executions` 添加 `tenant_id`；CREATE 3 个 enum 类型

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **enum 使用 PostgreSQL 原生类型，不选 String**：PostgreSQL enum 在 DB 层提供 compile-time 约束，插入非法值直接报错，优于应用层独自校验
- **workflow_steps 用 instance_id 而非 execution_id 做外键**：同一 workflow 可并发运行多个 execution，step execution 必须绑定到具体 execution instance，而非 workflow 定义本身；`workflow_step_executions.instance_id` 是执行记录的唯一标识
- **tenant_id 复合索引而非单列索引**：多租户查询总是 `WHERE tenant_id = X`，复合索引 `(tenant_id, <col>)` 支持覆盖索引，无需回表

### 4.2 版本约束

（无新依赖引入，整段删掉）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 现有 `workflows` 表的 `status` 列在 `b2c3dce4b714_create_all_tables.py` 中定义为 `String(50)` — ALTER 仅新增 enum 类型，不修改现有列类型，保证向后兼容

### 4.4 已知坑

1. **Alembic autogenerate 对 enum 类型不会生成 `CREATE TYPE` 语句** → 在 migration 中手动添加 3 个 `op.execute("CREATE TYPE ...")` 语句
2. **Alembic autogenerate 对 `tenant_id` 复合索引漏生成** → 显式用 `op.create_index()` 创建
3. **PostgreSQL enum 默认值需用 `'value'::step_status` 语法** → 迁移脚本中使用 `server_default=sa.text("'draft'::workflow_status")`
4. **PYTHONPATH=src**，import 路径写 `from db.models.workflow import ...`，不写 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 准备 alembic_dev 数据库（clean DB）

操作：
a) 确保 docker test-db 运行：`docker compose -f configs/docker-compose.test.yml up -d test-db`
b) 在 alembic_dev 上执行 clean create：

```bash
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
```

c) 设置环境变量并 bring to head：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

**完成判定**：`alembic current` 输出最新 revision，exit 0

---

### Step 2: 生成 migration 模板（autogenerate）

操作：
a) 执行 autogenerate：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic revision --autogenerate -m "add workflow tables with enums"
```

预期产出：`alembic/versions/<new_id>_add_workflow_tables.py`

**完成判定**：文件存在且 `alembic history --verbose` 显示新增 revision，down_revision 为 `c94d682d4b03`

---

### Step 3: 手工修正 migration — 添加 enum 类型 + tenant_id 列 + 所有索引

autogenerate 不会生成 PostgreSQL enum 类型，也不会生成 `tenant_id` 列。手动补全 `upgrade()` 函数，在 `op.create_table`之前先创建 3 个 enum 类型，并修改 `workflow_executions` 表添加 `tenant_id`：

操作：
a) 在 `upgrade()` 函数顶部 `op.create_table('workflow_steps', ...)` 之前插入 3 个 enum 创建语句：

```python
    op.execute("CREATE TYPE step_type AS ENUM ('manual', 'step', 'condition', 'branch', 'notify')")
    op.execute("CREATE TYPE step_status AS ENUM ('pending', 'running', 'success', 'failed', 'skipped')")
    op.execute("CREATE TYPE workflow_status AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled')")
```

b) 在 `upgrade()` 中添加 ALTER 语句（existing `workflow_executions` has no tenant_id）：

```python
    op.add_column('workflow_executions',
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_workflow_executions_tenant_id', 'workflow_executions', ['tenant_id'], unique=False)
    op.create_index('ix_workflow_executions_instance_id', 'workflow_executions', ['id'], unique=False)
```

c) 将 `workflows.status` 和 `workflow_executions.status` 列的默认值改为 enum cast：

```python
    op.alter_column('workflows', 'status',
        existing_type=sa.String(length=50),
        server_default=sa.text("'draft'::workflow_status"))
```

d) 在 `downgrade()` 函数末尾添加对应 drop：

```python
    op.execute("DROP TYPE IF EXISTS workflow_status")
    op.execute("DROP TYPE IF EXISTS step_status")
    op.execute("DROP TYPE IF EXISTS step_type")
```

完整 `upgrade()` 结构（3 个 enum + 2 个 new tables + ALTER existing）：

```python
def upgrade() -> None:
    # 1. Create PostgreSQL enum types
    op.execute("CREATE TYPE step_type AS ENUM ('manual', 'step', 'condition', 'branch', 'notify')")
    op.execute("CREATE TYPE step_status AS ENUM ('pending', 'running', 'success', 'failed', 'skipped')")
    op.execute("CREATE TYPE workflow_status AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled')")

    # 2. ALTER existing workflow_executions: add tenant_id + indexes
    op.add_column('workflow_executions',
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default=sa.text("'0'")))
    op.create_index('ix_workflow_executions_tenant_id', 'workflow_executions', ['tenant_id'], unique=False)
    op.create_index('ix_workflow_executions_instance_id', 'workflow_executions', ['id'], unique=False)

    # 3. Create workflow_steps table
    op.create_table('workflow_steps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('step_type', sa.Enum('manual', 'step', 'condition', 'branch', 'notify', name='step_type'), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_steps_workflow_id'), 'workflow_steps', ['workflow_id'], unique=False)
    op.create_index('ix_workflow_steps_tenant_workflow', 'workflow_steps', ['tenant_id', 'workflow_id'], unique=False)

    # 4. Create workflow_step_executions table
    op.create_table('workflow_step_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=False),
        sa.Column('instance_id', sa.String(length=100), nullable=False, index=True),
        sa.Column('step_type', sa.String(length=20), nullable=False),
        sa.Column('step_status', sa.Enum('pending', 'running', 'success', 'failed', 'skipped', name='step_status'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_step_executions_tenant_instance', 'workflow_step_executions', ['tenant_id', 'instance_id'], unique=False)
    op.create_index(op.f('ix_workflow_step_executions_execution_id'), 'workflow_step_executions', ['execution_id'], unique=False)
```

**完成判定**：`ruff check alembic/versions/<new_id>_add_workflow_tables.py` → 0 errors

---

### Step 4: 验证 migration 可双向执行

操作：
a) `alembic upgrade head`
b) `alembic downgrade -1`
c) `alembic upgrade head`

**完成判定**：三次命令全部 exit 0，无错误输出

---

### Step 5: 检查无 residual drift

操作：
a) `alembic revision --autogenerate -m "drift_check"`
b) 检查生成的文件 — 若 `upgrade()` 和 `downgrade()` 函数体仅含 `pass`，则无 drift，可删除该空 migration 文件；若非空则需继续修正

**完成判定**：空 migration 文件存在（可删除）或确认无 drift

---

### Step 6: 编写单元测试

创建 `tests/unit/test_workflow_model.py`，3 个测试用例：

```python
import pytest
from datetime import datetime
from src.db.models.workflow import WorkflowModel, WorkflowExecutionModel

# Test 1: WorkflowModel.to_dict 包含所有字段
def test_workflow_model_to_dict():
    model = WorkflowModel(
        id=1, tenant_id=42, name="Test Workflow",
        description="A test", trigger_type="manual",
        trigger_config={}, actions=[], conditions=[],
        status="draft", created_by=1,
        created_at=datetime(2026, 5, 29, 12, 0, 0),
        updated_at=datetime(2026, 5, 29, 12, 0, 0),
    )
    d = model.to_dict()
    assert d["id"] == 1
    assert d["tenant_id"] == 42
    assert d["name"] == "Test Workflow"
    assert d["status"] == "draft"
    assert d["trigger_type"] == "manual"

# Test 2: WorkflowExecutionModel.to_dict 包含 result 字段
def test_workflow_execution_to_dict():
    model = WorkflowExecutionModel(
        id=1, workflow_id=10, trigger_type="manual",
        triggered_by=1, started_at=datetime(2026, 5, 29, 12, 0, 0),
        status="running", result={"steps": 3},
    )
    d = model.to_dict()
    assert d["workflow_id"] == 10
    assert d["status"] == "running"
    assert d["result"] == {"steps": 3}

# Test 3: WorkflowModel 默认 status 为 draft
def test_workflow_model_default_status():
    model = WorkflowModel(
        id=1, tenant_id=1, name="X",
        trigger_type="manual", status="draft",
        created_by=1, created_at=datetime.now(), updated_at=datetime.now(),
    )
    assert model.status == "draft"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_model.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check alembic/versions/<new_id>_add_workflow_tables.py` → 0 errors
- [ ] `alembic upgrade head` → exit 0
- [ ] `alembic downgrade -1` → exit 0
- [ ] `alembic upgrade head` → exit 0（三次连续验证）
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_model.py -v` → `3 passed`
- [ ] `alembic revision --autogenerate -m "drift_check"` → 空 migration（无 residual drift）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| PostgreSQL enum 添加后无法 drop 类型（被列引用）导致 downgrade 失败 | 低 | 中 | downgrade 时先 DROP COLUMN 再 DROP TYPE，或改用 `IF EXISTS` + 忽略报错 |
| `workflow_executions` 表已有数据时 ALTER 添加 NOT NULL 列（server_default='0'）需全表锁 | 低 | 中 | 数据量小（开发/测试环境），生产若有数据需用 `ALTER ... SET DEFAULT` + batch backfill |
| autogenerate 对 enum 列产生空 migration（ORM 模型无 enum 声明） | 低 | 高 | 手动写完整 migration（参考 Step 3 代码片段） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add alembic/versions/<new_id>_add_workflow_tables.py
git add tests/unit/test_workflow_model.py
git commit -m "feat(workflows): add workflow tables migration with PostgreSQL enums and indexes

Closes #660"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#660): add alembic migration for workflow tables" --body "Closes #660

## Summary
- Add PostgreSQL enum types: step_type, step_status, workflow_status
- Create workflow_steps and workflow_step_executions tables
- Add tenant_id column and indexes to workflow_executions
- All migrations reversible (upgrade/downgrade/upgrade exit 0)"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现（ORM model + existing workflow tables）：[`src/db/models/workflow.py`](../../../src/db/models/workflow.py) — `WorkflowModel` 和 `WorkflowExecutionModel` 定义参考
- 同类参考实现（migration with enum pattern）：[`alembic/versions/9d8e7f6a5b3c_add_auth_tables.py`](../../../alembic/versions/9d8e7f6a5b3c_add_auth_tables.py) — 多表 + FK + 索引的 migration 风格
- 同类参考实现（JSONB + composite index）：TBD - 待验证：automation 相关 model 文件路径待确认
- 父 issue / 关联：#651, #659

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

-----

**修复说明：**

- **Line 10**：链接 `50-automation/0685-implement-ruleservice-with-crud-operations.md` 改为 `../../50-automation/0685-implement-ruleservice-with-crud-operations.md`（从 `00-foundations/` 出发需向上两级目录）
- **Line 397**（Section 9 参考）：该文件 `src/db/models/automation.py` 在代码库中不存在（只有 `automation_rule.py` 与 `automation_log.py`），改为 `TBD - 待验证：automation 相关 model 文件路径待确认`
