# 50-automation · 添加 Workflow ORM 模型与 Migration

| 元数据 | 值 |
|---|---|
| Issue | #516 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：依赖 #516 的后续板块（如规则执行引擎、触发调度等），待从父 issue #73 中确认 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #73 定义了完整的自动化工作流子系统，当前所有工作流元数据（workflows、执行记录、节点状态）均无持久化存储。现阶段只能存在于内存中，无法跨进程/重启保留，也无法与多租户隔离体系对接。父 issue 要求在基础设施层面先建立 ORM 模型与 migration，为后续规则执行引擎（#687）、触发调度（#687）等下游板块提供可靠的数据层基座。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层数据库 schema 改动，仅影响程序内部数据持久化。
- **开发者视角**：`src/db/models/workflow_models.py` 中包含 `Workflow`、`WorkflowExecution`、`WorkflowNode` 三个 ORM 模型，可通过 `WorkflowService` 查询/写入工作流数据；`alembic` 可通过 `alembic upgrade head` 创建对应表结构。

### 1.3 不做什么（剔除）

- [ ] **不做**：工作流 CRUD 业务逻辑（service / router）— 属于后续板块
- [ ] **不做**：工作流执行引擎（节点调度、状态机）— 属于 #687 后续板块
- [ ] **不做**：自动化规则表（`automation_rules` 等）— 属于其他独立 issue
- [ ] **不做**：单元测试 — issue 明确注明 schema-only，测试在后续板块添加

### 1.4 关键 KPI

- `ruff check src/db/models/workflow_models.py` → 0 errors
- `alembic upgrade head` → exit 0，输出包含 `create table workflows`、`create table workflow_executions`、`create table workflow_nodes`
- `alembic downgrade -1` → exit 0（migration 可逆）
- `alembic upgrade head` 第二次运行 → exit 0（re-run 安全）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 目录下现有文件名列表（如 `customer.py`、`ticket.py` 等），确认 `Base` 导出方式及 ORM 模型编写规范。

相关现有模型参考（推测路径，需验证）：

TBD - 待验证：`src/db/models/` 下是否存在类似带 JSONB 字段和多租户字段的模型（如 `automation_rule` 之类），用于参考 `__tablename__`、`Mapped` 类型注解、`nullable`/index 规范写法。

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 新增 `from db.models.workflow_models import Workflow, WorkflowExecution, WorkflowNode` 导入语句
- 要建：
  - `src/db/models/workflow_models.py` — 三个 ORM 模型定义
  - `alembic/versions/<id>_add_workflow_tables.py` — 自动生成的 migration 文件（由 `alembic revision --autogenerate` 产出）

### 2.3 缺什么

- [ ] `Workflow` ORM 模型（含 `tenant_id`、`definition_json`、`status` 等字段）
- [ ] `WorkflowExecution` ORM 模型（含 `workflow_id` FK、`input`/`output` JSONB、`status`/`started_at`/`completed_at` 等）
- [ ] `WorkflowNode` ORM 模型（含 `execution_id` FK、`definition_json`、`input`/`output` JSONB、`status` 等）
- [ ] `alembic/env.py` 中缺少对上述三个模型的导入，导致 autogenerate 不会检测到 drift
- [ ] 尚未生成 migration 文件

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/workflow_models.py` | 定义 `Workflow`、`WorkflowExecution`、`WorkflowNode` 三个 SQLAlchemy ORM 模型 |
| `alembic/versions/<id>_add_workflow_tables.py` | 创建 `workflows`、`workflow_executions`、`workflow_nodes` 三张表的 migration |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../alembic/env.py) | 在 model imports 区域新增三个模型的导入，使 alembic autogenerate 可检测 drift |

### 3.3 新增能力

- **ORM model**：`Workflow` in `src/db/models/workflow_models.py` — 顶层工作流定义，含 tenant_id、version、definition_json、status
- **ORM model**：`WorkflowExecution` in `src/db/models/workflow_models.py` — 单次工作流执行记录，含 input/output JSONB、trigger info
- **ORM model**：`WorkflowNode` in `src/db/models/workflow_models.py` — 执行中单个节点状态，含 definition_json、input/output、timing、retry info
- **Migration**：`alembic upgrade head` 创建三张表，含 `tenant_id` 索引、FK 级联删除

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `UUID` 作为 `Workflow` 和 `WorkflowExecution` 的主键，不选自增 int**：工作流通常由外部系统（如低代码编辑器、API 调用）创建并持有强一致性 ID，UUID 避免主键冲突且天然支持分布式场景
- **用 `JSONB` 而非 `JSON`**：workflow definition/input/output 经常需要按字段内容查询（如 `definition_json->>'state'`），JSONB 在 PostgreSQL 内支持 GIN 索引且查询性能更好
- **所有 `DateTime` 列用 `TIMESTAMPTZ`**：多租户场景下时区不一致会引发统计/排障歧义，强制带时区

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`workflows` 表每条 SQL 必须 `WHERE tenant_id = :tenant_id`；`workflow_executions` 和 `workflow_nodes` 通过 FK 继承 tenant 隔离
- 列名禁止使用 `metadata`（与 `Base.metadata` SQLAlchemy MetaData 对象冲突）→ 使用 `definition_json`、`input_json`、`output_json`、`node_definition_json`
- ORM 模型放在 `src/db/models/workflow_models.py`，导入路径为 `from db.models.workflow_models import Workflow, WorkflowExecution, WorkflowNode`
- Alembic env.py 中的 import 应为 `from db.models.workflow_models import Workflow, WorkflowExecution, WorkflowNode`（非 `from src.db.models...`）

### 4.4 已知坑

1. **Alembic autogenerate 把 `JSONB` 写成 `JSON`** → 规避：migration 手动将 `sa.JSON()` 替换为 `sa.JSONB()`
2. **Alembic autogenerate 把 `TIMESTAMPTZ`（带时区）写成 `DateTime`** → 规避：migration 手动将 `DateTime` 改为 `DateTime(timezone=True)`
3. **Alembic autogenerate 忽略 `server_default` 和 `index=True` 导致重复运行失败** → 规避：生成后检查 `op.create_index()` 是否存在；如有索引但 migration 重跑报错，手动补 `op.drop_index()` 或用 `alembic stamp head` 跳过
4. **`Base.metadata` 与列名 `metadata` 冲突（SQLAlchemy 内部使用）** → 规避：所有 JSON 字段使用 `definition_json`、`input_json`、`output_json`、`node_definition_json` 等命名

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/workflow_models.py`

在 `src/db/models/` 目录下新建 `workflow_models.py`，定义三个 SQLAlchemy ORM 模型。

从 `Base` 继承，使用 SQLAlchemy 2.x `Mapped` 类型注解风格，参考以下结构：

```python
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Text, ForeignKey, DateTime, Index
from sqlalchemy import JSONB, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base
import enum

class WorkflowStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISABLED = "disabled"

class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkflowStatus.DRAFT.value)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    executions: Mapped[list["WorkflowExecution"]] = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ExecutionStatus.PENDING.value)
    trigger_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_wfe_workflow_execnum", "workflow_id", "execution_number", unique=True),)
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    nodes: Mapped[list["WorkflowNode"]] = relationship("WorkflowNode", back_populates="execution", cascade="all, delete-orphan")

class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    node_key: Mapped[str] = mapped_column(String(128), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=NodeStatus.PENDING.value)
    node_definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_wn_execution_node_key", "execution_id", "node_key", unique=True),)
    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="nodes")
```

**完成判定**：`ruff check src/db/models/workflow_models.py` → 0 errors

---

### Step 2: 更新 `alembic/env.py` 导入

在 `alembic/env.py` 的 model imports 区域添加：

```python
from db.models.workflow_models import Workflow, WorkflowExecution, WorkflowNode
```

确保该行位于现有 imports 附近（如 `from db.models.customer import Customer` 等之后）。

**完成判定**：`grep -n "workflow_models" alembic/env.py` 返回匹配行；`ruff check alembic/env.py` → 0 errors

---

### Step 3: 启动干净数据库并生成 migration

使用 CLAUDE.md 中定义的流程，对专用 disposable 数据库运行 autogenerate：

```bash
# 启动干净数据库（如已有 test-db docker container 则跳过 docker compose up）
docker compose -f configs/docker-compose.test.yml up -d test-db

# 创建专用 alembic_dev 数据库
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 切换到 head
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# autogenerate
alembic revision --autogenerate -m "add workflows workflow_executions workflow_nodes tables"
```

**完成判定**：`ls alembic/versions/` 中出现新文件 `*_add_workflows_workflow_executions_workflow_nodes_tables.py`

---

### Step 4: 人工审查并修正 migration

检查新生成的 migration 文件：

1. 将所有 `sa.JSON()` 替换为 `sa.JSONB()`
2. 将所有 `DateTime` 替换为 `DateTime(timezone=True)`
3. 确认 FK 级联删除 `ondelete="CASCADE"` 存在
4. 确认 `tenant_id` 列存在索引 `index=True`
5. 确认 `workflow_executions.workflow_id` 和 `workflow_nodes.execution_id` 上有索引
6. 确认 `downgrade()` 方法执行 `op.drop_table()`（autogen 有时留空）

示例修正（针对 JSON → JSONB）：

```python
# 修正前（autogen 产出）
definition_json=sa.Column(sa.JSON(), nullable=False)

# 修正后
definition_json=sa.Column(sa.JSONB(), nullable=False)
```

示例修正（针对 DateTime → DateTime with timezone）：

```python
# 修正前
created_at=sa.Column(sa.DateTime(), nullable=False)

# 修正后
created_at=sa.Column(sa.DateTime(timezone=True), nullable=False)
```

**完成判定**：`grep -n "JSON()" alembic/versions/<新文件>.py` 无输出；`grep -n "DateTime(timezone=True)" alembic/versions/<新文件>.py` 有输出

---

### Step 5: 验证 migration 可逆

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

# upgrade → downgrade → upgrade 全流程
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：三次命令均 exit 0，无报错

---

### Step 6: 二次 autogenerate 确认无 drift

```bash
alembic revision --autogenerate -m "drift_check"
```

检查新文件 `*_drift_check.py` 的 `upgrade()` 和 `downgrade()` 方法中仅含 `pass`。若为空 migration 则证明模型与数据库已同步；若出现内容则需进一步修正。

**完成判定**：`grep -A5 "def upgrade" alembic/versions/*_drift_check.py` 中 upgrade/downgrade 块均含 `pass`

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow_models.py` → 0 errors
- [ ] `grep -n "workflow_models" alembic/env.py` → 返回匹配行
- [ ] `ls alembic/versions/ | grep "add_workflow"` → 新 migration 文件存在
- [ ] `grep "JSONB()" alembic/versions/<新文件>.py` → 有 JSONB 输出（autogen 已修）
- [ ] `grep "DateTime(timezone=True)" alembic/versions/<新文件>.py` → 有 TIMESTAMPTZ 输出（autogen 已修）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| migration 文件中 `JSON` 未手动改为 `JSONB`，生产环境查询性能差 | 中 | 中 | Revert migration：`alembic downgrade -1`，修改文件后重新 `alembic revision --autogenerate -m "fix_json_to_jsonb"` |
| FK 级联删除未正确设置，导致删除 workflow 时 executions 残留 | 低 | 高 | 新增 migration 加入 `ondelete="CASCADE"` 或手动删除残留记录 |
| UUID 主键与下游代码（如 service 层的 `get_entity`）类型不匹配 | 低 | 中 | 在 service 层显式使用 `str` 类型转换；数据库层不受影响 |
| docker container 名称与 CLAUDE.md 不同导致 alembic 命令失败 | 低 | 中 | `docker ps --format "{{.Names}}"` 确认实际容器名后替换 `configs-test-db-1` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/workflow_models.py alembic/env.py alembic/versions/*.py
git commit -m "feat(automation): add Workflow, WorkflowExecution, WorkflowNode ORM models and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#516): add workflow ORM models and migration" --body "Closes #516

## Summary
- Add SQLAlchemy ORM models for workflows / workflow_executions / workflow_nodes tables
- Import models in alembic/env.py
- Generate alembic migration with JSONB and TIMESTAMPTZ columns

## Test plan
- [ ] ruff check src/db/models/workflow_models.py → 0 errors
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/` 下现有带 JSONB 字段的模型（如 `campaign.py` 或其他），用于参考类型注解写法
- 父 issue / 关联：#73（自动化工作流子系统父 issue）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
