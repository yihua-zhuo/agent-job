# 工作流执行 ORM 模型与 Migration  · 创建 workflow_execution 和 workflow_node 表

| 元数据 | 值 |
|---|---|
| Issue | #736 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0737-implement-node-base-class-and-placeholder-nodes](../50-automation/0737-implement-node-base-class-and-placeholder-nodes.md), [0738-implement-workflowengine-with-topological-sort](../50-automation/0738-implement-workflowengine-with-topological-sort.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #517 的目标是将工作流任务自动化框架引入本 CRM 系统。任务执行需要持久化记录：当前有哪些工作流正在执行、执行到哪一步、状态如何。当前数据库中无任何 workflow 相关的表，所有后续 engine 和 node 实现都依赖本板块创建的 schema。先建表再写代码，是正确的依赖顺序。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 本板块为纯底层 schema 改动。
- **开发者视角**：可通过 ORM 操作 `WorkflowExecution` 和 `WorkflowNodeExecution` 表；后续板块可以在此基础上实现 engine 和 node placeholder。

### 1.3 不做什么（剔除）

- [ ] 实现 WorkflowEngine 或节点调度逻辑（属于 #0738 板块）
- [ ] 创建 WorkflowNode 基类或任何 node placeholder（属于 #0737 板块）
- [ ] 添加 service 层或 API router（本板块仅建 ORM + migration）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_workflow_execution.py -v` → 全 passed（等效于至少 1 个模型存在且可实例化）]
- [指标 2：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0]
- [指标 3：`ruff check src/db/models/workflow_execution.py src/db/models/workflow_node.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 下是否有 workflow 相关文件 — 当前应为空白，不存在任何 workflow ORM 模型

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../../alembic/env.py) — 追加新的 workflow model import，使 autogen 可识别
- 要建：
  - `src/db/models/workflow_execution.py` — WorkflowExecution ORM model + ExecutionStatus 枚举
  - `src/db/models/workflow_node.py` — WorkflowNodeExecution ORM model
  - `alembic/versions/<id>_create_workflow_tables.py` — alembic autogenerate 生成的 migration（需手动修正）
  - `tests/unit/test_workflow_execution.py` — ORM 模型基础单元测试

### 2.3 缺什么

- [ ] 无 `WorkflowExecution` 表 — 无法记录工作流实例的启动时间、执行状态、结束时间]
- [ ] 无 `ExecutionStatus` 枚举 — 各状态（PENDING / RUNNING / COMPLETED / FAILED / CANCELLED）无统一类型]
- [ ] 无 `WorkflowNodeExecution` 表 — 无法记录每个节点级别的执行状态]
- [ ] alembic/env.py 中无 workflow model import — autogen 无法感知新表]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/workflow_execution.py` | WorkflowExecution ORM model + ExecutionStatus 枚举 |
| `src/db/models/workflow_node.py` | WorkflowNodeExecution ORM model |
| `alembic/versions/<id>_create_workflow_tables.py` | 创建 workflow_execution 和 workflow_node_execution 表的 migration |
| `tests/unit/test_workflow_execution.py` | WorkflowExecution 和 WorkflowNodeExecution 模型的基础单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../../alembic/env.py) | 追加 `from db.models.workflow_execution import WorkflowExecution, ExecutionStatus` 和 `from db.models.workflow_node import WorkflowNodeExecution` |

### 3.3 新增能力

- **ORM model**：`WorkflowExecution` in `src/db/models/workflow_execution.py`（含 ExecutionStatus enum）
- **ORM model**：`WorkflowNodeExecution` in `src/db/models/workflow_node.py`
- **Migration**：`alembic upgrade head` 创建 `workflow_execution` 表（含 `tenant_id` 索引）和 `workflow_node_execution` 表（含 `tenant_id` 索引）
- **Enum type**：Postgres `workflow_execution_status` enum 类型，通过 migration 创建

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `execution_status` 作为 enum 而非字符串**：Postgres 原生 enum 类型比 varchar 更节省空间且有类型约束，防止写入非法状态值
- **选 `TIMESTAMPTZ`（带时区）而非 `DATE` 或 `DATETIME` 不带时区**：CRM 为多租户系统，tenant 可在不同 timezone 操作，带时区时间戳避免歧义
- **选 `JSONB` 而非 `JSON`**：workflow node payload 通常需要索引，JSONB 支持 GIN 索引且解析更快

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每张表必须有 `tenant_id` 列且建立索引（见 CLAUDE.md §Multi-Tenancy）
- SQLAlchemy：ORM model 的列名**不得**使用 `metadata`（与 `Base.metadata` 冲突），本板块使用 `execution_metadata` 字段名
- 表名：使用 snake_case（SQLAlchemy 默认），与 Postgres 命名规范一致
- Migration：upgrade / downgrade 必须成对，revert 后数据不留痕

### 4.4 已知坑

1. **Alembic autogen 把 `JSONB` 误写成 `sa.JSON()`** → 规避：autogenerate 后手动将 `sa.JSON()` 改回 `sa.JSONB()`
2. **Alembic autogen 把 `TIMESTAMPTZ` 误写成 `sa.DateTime()`** → 规避：autogenerate 后将 `DateTime` 改为 `DateTime(timezone=True).with_variant(MutableType(), 'postgresql')` 或直接用 `postgresql.TIMESTAMPTZ`
3. **SQLAlchemy Base 子类列名使用 `metadata` 与 `Base.metadata` 冲突** → 规避：使用 `execution_metadata` 或 `payload` 作为 JSONB 字段名
4. **PYTHONPATH=src，import 须写 `from db.models...`** → 规避：所有 import 均为 `from db.models.workflow_execution import ...`，不得写 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 workflow_execution.py（含 ExecutionStatus enum）

在 `src/db/models/` 下新建 `workflow_execution.py`。

文件内容：

```python
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from db.base import Base


class ExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowExecution(Base):
    __tablename__ = "workflow_execution"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(nullable=False)
    execution_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_workflow_execution_tenant_status", "tenant_id", "status"),
        Index("ix_workflow_execution_tenant_key", "tenant_id", "workflow_key"),
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow_execution import WorkflowExecution, ExecutionStatus; print('OK')"` → 输出 `OK`，无 ImportError

---

### Step 2: 创建 workflow_node.py（WorkflowNodeExecution）

在 `src/db/models/` 下新建 `workflow_node.py`。

文件内容：

```python
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from db.base import Base


class WorkflowNodeExecution(Base):
    __tablename__ = "workflow_node_execution"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("workflow_execution.id", ondelete="CASCADE"), nullable=False)
    node_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_workflow_node_execution_tenant_execution", "tenant_id", "execution_id"),
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow_node import WorkflowNodeExecution; print('OK')"` → 输出 `OK`，无 ImportError

---

### Step 3: 在 alembic/env.py 中添加 model import

在 `alembic/env.py` 的 import 区块追加：

```python
from db.models.workflow_execution import WorkflowExecution, ExecutionStatus
from db.models.workflow_node import WorkflowNodeExecution
```

确保新增 import 位于文件顶部，与其他 `from db.models...` import 保持风格一致。

**完成判定**：`PYTHONPATH=src python -c "import alembic.config; print('OK')"` → 无报错（验证语法正确）

---

### Step 4: 启动 test docker DB 并生成 migration

```bash
# 4a. 启动干净 DB
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 4b. 执行到 head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# 4c. 生成 migration
alembic revision --autogenerate -m "create workflow_execution and workflow_node_execution tables"
```

**完成判定**：命令 exit 0 且 `alembic/versions/` 下生成新文件

---

### Step 5: 手动修正 autogenerate 生成的 migration

用 Read 工具打开 Step 4 生成的文件，检查并修正：

1. 将所有 `sa.JSON()` 替换为 `sa.JSONB()`
2. 将所有 `DateTime`（不带 timezone=True）替换为 `DateTime(timezone=True)`
3. 确认 `status` 列使用 `Enum(...)` 类型而非 plain varchar
4. 确认 `tenant_id` 列有 `index=True`
5. 确认 downgrade 部分为 `op.drop_table(...)` 干净回滚

**完成判定**：`ruff check alembic/versions/<新文件>` → 0 errors

---

### Step 6: 验证 migration 往返

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

alembic upgrade head
# 预期：创建 workflow_execution 和 workflow_node_execution 表，exit 0

alembic downgrade -1
# 预期：删除两张表，exit 0

alembic upgrade head
# 预期：重新创建，exit 0
```

**完成判定**：三次命令均 exit 0，且第三次 upgrade 后执行 `alembic current` 显示最新 revision

---

### Step 7: 编写基础 ORM 单元测试

在 `tests/unit/` 下新建 `test_workflow_execution.py`，测试：

- `WorkflowExecution` 和 `WorkflowNodeExecution` 可被正确实例化
- `ExecutionStatus` 枚举所有值可访问（PENDING / RUNNING / COMPLETED / FAILED / CANCELLED）
- Mock session 下的 SELECT 查询返回空列表（初始状态）

参考其他单元测试文件的 fixture 写法：

```python
import pytest
from tests.unit.conftest import MockState, make_mock_session

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])

def test_execution_status_enum():
    from db.models.workflow_execution import ExecutionStatus
    assert ExecutionStatus.PENDING.value == "PENDING"
    assert ExecutionStatus.RUNNING.value == "RUNNING"
    assert ExecutionStatus.COMPLETED.value == "COMPLETED"
    assert ExecutionStatus.FAILED.value == "FAILED"
    assert ExecutionStatus.CANCELLED.value == "CANCELLED"

def test_workflow_execution_model_exists(mock_db_session):
    from db.models.workflow_execution import WorkflowExecution
    assert hasattr(WorkflowExecution, "__tablename__")
    assert WorkflowExecution.__tablename__ == "workflow_execution"

def test_workflow_node_execution_model_exists(mock_db_session):
    from db.models.workflow_node import WorkflowNodeExecution
    assert hasattr(WorkflowNodeExecution, "__tablename__")
    assert WorkflowNodeExecution.__tablename__ == "workflow_node_execution"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_execution.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow_execution.py src/db/models/workflow_node.py alembic/env.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.workflow_execution import WorkflowExecution, ExecutionStatus; from db.models.workflow_node import WorkflowNodeExecution; print('OK')"` → 输出 `OK`
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_execution.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogen 生成的 migration 遗漏 tenant_id 索引 | 低 | 高 | 手动在 migration 中补 `op.create_index("ix_workflow_execution_tenant_id", "workflow_execution", ["tenant_id"])` |
| enum 类型与其他模块冲突 | 低 | 中 | 改为在 Python 层用 str enum，DB 层用 varchar，避免创建 Postgres enum type |
| docker test-db 启动失败（端口占用） | 低 | 中 | `docker compose -f configs/docker-compose.test.yml down && docker compose -f configs/docker-compose.test.yml up -d` 重试 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/workflow_execution.py src/db/models/workflow_node.py alembic/env.py alembic/versions/ tests/unit/test_workflow_execution.py
git commit -m "feat(workflow): add WorkflowExecution and WorkflowNodeExecution ORM models + migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(workflow): ORM models for workflow execution (#736)" --body "Closes #736"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/` 下现有 ORM model 的编写规范（如 `src/db/models/opportunity.py` 或 `src/db/models/ticket.py` 作为字段命名和表结构参考）
- 第三方文档：[SQLAlchemy 2.0 async ORM 文档](https://docs.sqlalchemy.org/en/20/orm/)，[Alembic autogenerate 指南](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- 父 issue / 关联：#517

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-30 | 创建 | TBD |
