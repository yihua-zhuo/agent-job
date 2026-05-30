# 新建 ORM 实体 · workflow_definitions 和 workflow_instances 两表| 元数据 | 值 |
|---|---|
| Issue | #657 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [rule-execution-engine](../50-automation/0687-build-rule-execution-engine-and-trigger-dispatch.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #651 的父任务是搭建自动化工作流引擎。引擎的运行时状态（触发条件 → 执行步骤 → 记录实例）需要持久化到 DB，而持久化依赖 SQLAlchemy ORM 模型。当前代码库中仅有 `WorkflowModel`（老版本，存 trigger/action/conditions 扁平结构）和 `WorkflowExecutionModel`，缺少版本化的**定义**模型（可存储多版本 JSON 蓝图）和**实例**模型（独立于 execution 的运行时上下文）。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 变更。
- **开发者视角**：`WorkflowDefinitionModel` 和 `WorkflowInstanceModel` 两个 ORM 类可直接被 service 层使用；所有 SQL 查询均按 `tenant_id` 隔离，具备多租户合规性。

### 1.3 不做什么（剔除）

- [ ] 不实现 workflow definition 的 CRUD service 层（属于后续板块 #651 细化范围）
- [ ] 不实现 workflow instance 的状态机和调度逻辑
- [ ] 不新增 API router（后续板块自行添加）
- [ ] 不在 `WorkflowDefinitionModel` 中冗余 trigger/action/conditions（已在 `WorkflowModel` 中存在，新表专攻"版本化蓝图"）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_workflow_definition_model.py tests/unit/test_workflow_instance_model.py -v` → ≥ 6 passed（两个文件各 3 个测试）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `ruff check src/db/models/workflow_definitions.py src/db/models/workflow_instances.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

已有 `workflow.py` 包含两个模型：

- [`src/db/models/workflow.py`](../../src/db/models/workflow.py) L{12}-L{47}：`WorkflowModel`（trigger/action/conditions 扁平结构，适合单版工作流）
- [`src/db/models/workflow.py`](../../src/db/models/workflow.py) L{49}-L{75}：`WorkflowExecutionModel`（执行记录，无 tenant_id 隔离）

db.models 包通过 [`src/db/models/__init__.py`](../../src/db/models/__init__.py) L{18}-L{24} 自动发现所有继承 `Base` 的类并注册到 `Base.metadata`，alembic 通过 `import db.models` 拾取所有模型。

现有模型中无版本化蓝图表，也无独立 instance 表。

### 2.2 涉及文件清单

- 要改：
  - 无（新增模型均独立文件，不破坏现有模型）
- 要建：
  - `src/db/models/workflow_definitions.py` — `WorkflowDefinitionModel`，版本化蓝图
  - `src/db/models/workflow_instances.py` — `WorkflowInstanceModel`，运行时实例
  - `alembic/versions/<id>_add_workflow_definitions_and_instances.py` — 建表迁移
  - `tests/unit/test_workflow_definition_model.py` — Blueprint 模型单元测试
  - `tests/unit/test_workflow_instance_model.py` — Instance 模型单元测试

### 2.3 缺什么

- [ ] `workflow_definitions` 表：存储多版本工作流蓝图（JSON 格式 definition_data）
- [ ] `workflow_instances` 表：存储每次触发的运行时上下文及状态- [ ] 两表均需 `tenant_id`隔离列和索引
- [ ] `workflow_instances` 需要 STATUS 枚举（pending / running / completed / failed / cancelled）
- [ ] 两模型需 `to_dict()` 方法供 router 层序列化
- [ ] Alembic 迁移脚本---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/workflow_definitions.py` | `WorkflowDefinitionModel`：版本化工作流蓝图，含 definition_data JSONB |
| `src/db/models/workflow_instances.py` | `WorkflowInstanceModel`：工作流实例，含 status枚举、context JSONB |
| `alembic/versions/<id>_add_workflow_definitions_and_instances.py` | 创建 `workflow_definitions` 和 `workflow_instances` 两表 |
| `tests/unit/test_workflow_definition_model.py` | Blueprint 模型：默认值、to_dict、tenant_id 字段测试 |
| `tests/unit/test_workflow_instance_model.py` | Instance 模型：默认值、to_dict、status枚举、tenant_id 字段测试 |

### 3.2 修改文件

（无 — 新模型独立文件，alembic 通过 pkgutil 已有 `import db.models` 自动感知）

### 3.3 新增能力

- **ORM model**：`WorkflowDefinitionModel` in `src/db/models/workflow_definitions.py`
- **ORM model**：`WorkflowInstanceModel`（含 `InstanceStatus` 枚举）in `src/db/models/workflow_instances.py`
- **Migration**：`alembic upgrade head` 创建 `workflow_definitions` 表（含 `tenant_id`、`definition_id` 索引）和 `workflow_instances` 表（含 `tenant_id`、`definition_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **定义数据列用 JSONB 而非 JSON**：`definition_data` 存储任意结构化工作流蓝图，JSONB 在 Postgres 中可建立 GIN 索引有利于后续按节点类型查询，且二进制存储避免字符转义歧义。
- **status 用 SQLAlchemy Enum 而非String**：`InstanceStatus` 显式枚举类型在 DB 层约束取值（pending/running/completed/failed/cancelled），避免拼写错误的脏数据。
- **不混用老 WorkflowModel/WorkflowExecutionModel**：新表 `workflow_definitions`专攻"版本化蓝图"，老 `workflows` 表保留给现有 trigger/action/conditions 工作流；两套并行，待后续板块完成迁移。
- **两表均加 `definition_id` 外键索引**：避免 JOIN 时全表扫描，`workflow_instances.definition_id` 加 B-Tree 索引（外键自带或显式加）。

### 4.2 版本约束

（无新引入依赖。JSONB、Enum均为 PostgreSQL / SQLAlchemy 内置特性。）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- 不在 `Base` 子类中使用列名 `metadata`（与 `Base.metadata` 冲突）→ 用 `definition_data` 已规避

### 4.4 已知坑

1. **Alembic autogenerate 把 JSONB写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 规避：autogenerate 完成后手动检查迁移文件，将 `JSON()`改回 `JSONB()`，`DateTime(timezone=True)` 确认存在2. **Alembic autogenerate 可能忽略新模型（仅当 `import db.models` 未拾取）** → 规避：确认 `alembic/env.py` 第14 行 `import db.models` 在新模型文件创建后再跑 autogen，或手动在迁移文件中 import 两个新模型类---

## 5. 实现步骤（按顺序）

### Step 1: 创建 WorkflowDefinitionModel

新建 `src/db/models/workflow_definitions.py`，定义蓝图 ORM 模型。

字段：
- `id`: Integer PK, autoincrement
- `tenant_id`: Integer, nullable=False, index=True
- `name`: String(255), nullable=False
- `description`: Text, nullable=True
- `version`: String(20), nullable=False（格式如 "1.0.0"）
- `definition_data`: JSONB, nullable=False, default=dict
- `created_at`: DateTime(timezone=True), server_default=func.now()
- `updated_at`: DateTime(timezone=True), server_default=func.now(), onupdate=func.now()

提供 `to_dict()` 方法序列化全部字段。

```python
# src/db/models/workflow_definitions.py
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class WorkflowDefinitionModel(Base):
    """Versioned workflow blueprint stored in DB."""
    __tablename__ = "workflow_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    definition_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "definition_data": self.definition_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow_definitions import WorkflowDefinitionModel; print('ok')"` exit 0

---

### Step 2: 创建 WorkflowInstanceModel（含 InstanceStatus 枚举）

新建 `src/db/models/workflow_instances.py`。

用 `from sqlalchemy import Enum, ForeignKey` 引入_status枚举约束。
`InstanceStatus` 使用 `Enum(name="workflow_instance_status", values_callable=lambda x: [...])` 映射 DB 值。

字段：
- `id`: Integer PK, autoincrement
- `tenant_id`: Integer, nullable=False, index=True
- `definition_id`: Integer FK → `workflow_definitions.id`, nullable=False, index=True
- `status`: InstanceStatus 枚举列，nullable=False，默认 pending
- `context`: JSONB, nullable=False, default=dict
- `started_at`: DateTime(timezone=True), server_default=func.now()
- `completed_at`: DateTime(timezone=True), nullable=True

```python
# src/db/models/workflow_instances.py
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class InstanceStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowInstanceModel(Base):
    """Runtime instance of a workflow definition."""
    __tablename__ = "workflow_instances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[InstanceStatus] = mapped_column(
        Enum(InstanceStatus, name="workflow_instance_status", create_constraint=True),
        default=InstanceStatus.PENDING,
        nullable=False,
    )
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "definition_id": self.definition_id,
            "status": self.status.value if self.status else None,
            "context": self.context or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow_instances import WorkflowInstanceModel, InstanceStatus; print('ok')"` exit 0

---

### Step 3: 生成 Alembic 迁移脚本

参考已有迁移文件格式（如 `alembic/versions/c94d682d4b03_add_ai_conversations.py`），确认 alembic/env.py 第 14 行已有 `import db.models`，新模型文件被 pkgutil 扫描后执行：

```bash
export PYTHONPATH=src
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade head
alembic revision --autogenerate -m "add workflow_definitions and workflow_instances"
```

autogenerate 完成后，手动审查生成的迁移文件 `alembic/versions/<id>_add_workflow_definitions_and_instances.py`：
- `create_table("workflow_definitions", ...)` 中所有 JSON 列使用 `JSONB()`
- `create_table("workflow_instances", ...)` 中 `sa.ForeignKey('workflow_definitions.id')` 正确
- 确认 `tenant_id` 列上有 `server_default='0'` 以及 `index=True`
- 两表 `downgrade()` 实现完整 drop（DROP TABLE顺序先 instances 后 definitions）

**完成判定**：`ruff check alembic/versions/*.py` →0 errors；`PYTHONPATH=src alembic upgrade head` exit 0

---

### Step 4: 编写单元测试 test_workflow_definition_model.py

在 `tests/unit/test_workflow_definition_model.py` 编写三个测试（参考 `tests/unit/test_customer_model.py` 结构，使用 `from src.models.workflow_definitions import WorkflowDefinition`导入，如路径差异则用 `from db.models.workflow_definitions import WorkflowDefinitionModel`）：

```python
# tests/unit/test_workflow_definition_model.py
from __future__ import annotations
import pytest
from datetime import datetime

# 如模型在 src/models/ 导出则 from src.models.workflow_definitions import ...
# 目前确认路径后用实际 importfrom db.models.workflow_definitions import WorkflowDefinitionModel


class TestWorkflowDefinitionModel:
    """Tests for WorkflowDefinitionModel."""

    def test_create_with_defaults(self):
        """All default fields are set on construction."""
        model = WorkflowDefinitionModel(
            name="Onboarding",
            version="1.0.0",
        )
        assert model.name == "Onboarding"
        assert model.version == "1.0.0"
        assert model.tenant_id == 0
        assert model.description is None
        assert model.definition_data == {}
        assert isinstance(model.created_at, datetime)

    def test_to_dict(self):
        """to_dict returns all fields including nested JSON."""
        model = WorkflowDefinitionModel(
            id=1,
            tenant_id=5,
            name="Sales",
            description="Sales funnel",
            version="2.1.0",
            definition_data={"steps": [{"type": "email"}]},
        )
        d = model.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 5
        assert d["name"] == "Sales"
        assert d["version"] == "2.1.0"
        assert d["definition_data"] == {"steps": [{"type": "email"}]}

    def test_tenant_id_indexed(self):
        """tenant_id column is present and non-nullable."""
        model = WorkflowDefinitionModel(name="Test", version="0.1.0")
        assert hasattr(model, "tenant_id")
        # nullable=False set in mapped_column
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_definition_model.py -v` → `3 passed`

---

### Step 5: 编写单元测试 test_workflow_instance_model.py

在 `tests/unit/test_workflow_instance_model.py` 编写三个测试：

```python
# tests/unit/test_workflow_instance_model.py
from __future__ import annotations
import pytest
from datetime import datetime

from db.models.workflow_instances import WorkflowInstanceModel, InstanceStatus


class TestWorkflowInstanceModel:
    """Tests for WorkflowInstanceModel."""

    def test_status_enum_values(self):
        """InstanceStatus covers all defined states."""
        assert InstanceStatus.PENDING.value == "pending"
        assert InstanceStatus.RUNNING.value == "running"
        assert InstanceStatus.COMPLETED.value == "completed"
        assert InstanceStatus.FAILED.value == "failed"
        assert InstanceStatus.CANCELLED.value == "cancelled"

    def test_create_with_defaults(self):
        """Default status is PENDING and context is empty dict."""
        model = WorkflowInstanceModel(definition_id=10, tenant_id=2)
        assert model.status == InstanceStatus.PENDING
        assert model.definition_id == 10
        assert model.tenant_id == 2
        assert model.context == {}
        assert model.completed_at is None
        assert isinstance(model.started_at, datetime)

    def test_to_dict(self):
        """to_dict serialises status.value and nested context."""
        model = WorkflowInstanceModel(
            id=7,
            tenant_id=3,
            definition_id=12,
            status=InstanceStatus.RUNNING,
            context={"trigger": "ticket.created", "ticket_id": 99},
        )
        d = model.to_dict()
        assert d["id"] == 7
        assert d["status"] == "running"
        assert d["context"] == {"trigger": "ticket.created", "ticket_id": 99}
        assert d["completed_at"] is None
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_instance_model.py -v` → `3 passed`

---

### Step 6: 验证迁移可双向操作

```bash
export PYTHONPATH=src
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
alembic downgrade -1
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

确认四次操作均 exit 0，且最后 `alembic current` 显示新 migration revision。

**完成判定**：`echo $?` → 0（四次管道均无错误），`alembic current` 显示 `<revision>`

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow_definitions.py src/db/models/workflow_instances.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.workflow_definitions import WorkflowDefinitionModel; from db.models.workflow_instances import WorkflowInstanceModel, InstanceStatus; print('ok')"` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_definition_model.py -v` → `3 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_instance_model.py -v` → `3 passed`
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic autogenerate 未识别新模型（pkgutil 扫描时机问题） | 低 | 高 |手动在 `alembic/env.py` 文件顶部加 `from db.models.workflow_definitions import WorkflowDefinitionModel; from db.models.workflow_instances import WorkflowInstanceModel` 后重新 autogenerate |
| autogenerate 把 JSONB 写成 JSON，DB 无 GIN 索引 | 低 | 中 | 手动编辑迁移文件，将 `JSON()`替换为 `JSONB()`（不影响 downgrades 只要两边一致） |
| 外键 ondelete=CASCADE 导致删 definition 时误删 instances | 低 | 高 | 如未来业务需保留实例记录，将 `ondelete="CASCADE"` 改为 `ondelete="SET NULL"`（需新建 migration 修改外键） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/workflow_definitions.py src/db/models/workflow_instances.py \
 alembic/versions/<id>_add_workflow_definitions_and_instances.py \
       tests/unit/test_workflow_definition_model.py tests/unit/test_workflow_instance_model.py
git commit -m "feat(automation): add WorkflowDefinitionModel and WorkflowInstanceModel ORM classes"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#657): add workflow_definitions and workflow_instances ORM models" --body "Closes #657"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/workflow.py`](../../src/db/models/workflow.py) —现有 `WorkflowModel` / `WorkflowExecutionModel` 作为模型结构参考
- 同类参考实现：[`src/db/models/automation.py`](../../src/db/models/automation.py) — `AutomationRuleModel` JSONB + tenant_id模式
- 父 issue /关联：#651

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
