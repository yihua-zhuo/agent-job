# DAG 执行引擎核心 · 实现 DAG 工作流执行引擎核心

| 元数据 | 值 |
|---|---|
| Issue | #517 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [DAG 节点模型抽象层](), [#516 节点模型抽象层](), [#73 工作流系统总览]() |
| 启用后赋能 | [#686 自动化规则 CRUD 路由](), [#687 规则执行引擎](), [#688 集成测试] |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `src/workflow/` 目录下没有任何执行引擎实现，workflow 定义无法被真正调度和运行。工作流节点拓扑排序、节点间输入/输出传递、以及执行状态的持久化均缺失，workflow 系统是一个空壳。实现 DAG 执行引擎核心是整个工作流系统的地基，后续所有节点类型和调度策略都依赖于此引擎。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 本板块为纯底层引擎实现。
- **开发者视角**：`WorkflowEngine` class 可接受 workflow 定义 JSON，通过 topological sort 确定执行顺序，顺序执行节点，将每步结果通过上下文 dict 在节点间传递，并将执行状态写入 `workflow_executions` / `workflow_nodes` 表。开发者可调用 `engine.run(workflow_def, tenant_id)` 启动一次执行。

### 1.3 不做什么（剔除）

- [ ] 实现具体的业务节点类型（如 HTTP 节点、脚本节点）— 仅放置返回 mock 输出的 placeholder 类
- [ ] 可视化 DAG UI / 流程图渲染
- [ ] 并行执行支持（本板块只做顺序执行）
- [ ] 重试策略、超时控制、断点续跑

### 1.4 关键 KPI

- [KPI 1：`PYTHONPATH=src pytest tests/unit/test_engine.py -v` → ≥ 4 passed（含 happy path 和 cycle-detection 场景）]
- [KPI 2：`ruff check src/workflow/` → 0 errors]
- [KPI 3：`ruff check tests/unit/test_engine.py` → 0 errors]
- [KPI 4：引擎对 A→B→C 无环 DAG 输出执行顺序 `[A, B, C]`，对含环 DAG 抛出 `ValidationException`]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/workflow/` 目录是否已存在；是否已有 `src/db/models/workflow*.py` 文件定义了 `workflow_executions` 和 `workflow_nodes` ORM 模型；`src/workflow/engine.py` 是否为空文件或尚不存在

现有代码片段（如 `src/workflow/` 已存在）：
```{1}:10:src/workflow/__init__.py
# placeholder if directory exists
```

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/workflow_execution.py` — 写入执行总览记录（若表已存在则引用，若不存在则新建）
  - `src/db/models/workflow_node.py` — 写入节点级执行记录（若表已存在则引用，若不存在则新建）
- 要建：
  - `src/workflow/engine.py` — DAG 执行引擎核心类
  - `src/workflow/nodes/` — 节点加载与 placeholder 节点实现目录
  - `alembic/versions/<id>_create_workflow_tables.py` — 若相关表不存在则新建 migration
  - `tests/unit/test_engine.py` — 引擎单元测试

### 2.3 缺什么

- [ ] DAG 执行引擎核心类 `WorkflowEngine`：接收 workflow JSON 定义，执行 topological sort，按序运行节点并传递 IO
- [ ] Topological sort 实现（含 cycle 检测）— 对有环图抛出 `ValidationException`
- [ ] `workflow_executions` 表的写入逻辑 — 执行启动时 INSERT，执行完成时 UPDATE status
- [ ] `workflow_nodes` 表的逐节点写入逻辑 — 每个节点执行后 INSERT 一条记录
- [ ] 节点加载机制：从 `src/workflow/nodes/` 按 `type` 字段动态实例化节点类
- [ ] Placeholder 节点类：实现节点接口、返回 mock 输出，不含真实业务逻辑
- [ ] 单元测试覆盖 happy path（正常 DAG 顺序执行）和 edge case（环检测）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/workflow/engine.py` | DAG 执行引擎：`WorkflowEngine` 类，含 `run()` 方法、topo sort、节点调度 |
| `src/workflow/nodes/__init__.py` | 节点注册与加载入口 |
| `src/workflow/nodes/base.py` | `WorkflowNode` 抽象基类，定义 `execute(ctx) -> dict` 接口 |
| `src/workflow/nodes/placeholder.py` | 各类 placeholder 节点实现（http、script、condition 等），返回 mock 输出 |
| `alembic/versions/<id>_create_workflow_tables.py` | 创建 `workflow_executions` / `workflow_nodes` 表（若表尚不存在） |
| `tests/unit/test_engine.py` | 引擎单元测试：happy path + cycle detection |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/workflow_execution.py` | 新增 `WorkflowExecution` ORM model（若尚不存在）— 含 status、started_at、completed_at、tenant_id 字段 |
| `src/db/models/workflow_node.py` | 新增 `WorkflowNode` ORM model（若尚不存在）— 含 execution_id、node_id、status、input、output、tenant_id 字段 |
| `alembic/env.py` | 导入新 ORM model 使 autogen 可发现（若新建 model） |

### 3.3 新增能力

- **Python class**：`WorkflowEngine` — 主执行引擎类，`__init__(session: AsyncSession)`，无 default session
- **Python class**：`WorkflowNode` — 节点抽象基类，`execute(ctx: dict) -> dict`
- **Service method**：`WorkflowExecutionService` — 持久化执行记录，遵循 CLAUDE.md service 规范
- **ORM model**：`WorkflowExecution` + `WorkflowNode`（multi-tenant，含 `tenant_id`）
- **Migration**：`alembic upgrade head` 创建/更新相关表
- **单元测试**：4+ 个测试用例覆盖 happy path、cycle detection、节点 IO 传递

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Topological sort 自己实现而非引入 `networkx`**：轻量无环图算法只需 Kahn's algorithm，引入 networkx 增加不必要依赖；cycle detection 已在 Kahn's algorithm 中天然覆盖（剩余节点非空但无人度为 0 → 有环）
- **节点加载用 dict 映射而非 `importlib` 动态导入**：`src/workflow/nodes/` 下的节点类型有限且可控，显式注册 mapping（`{"http": HttpNode, "script": ScriptNode}`）比反射更简洁、可维护、易测试
- **节点间 IO 通过 ctx dict 传递**而非序列化到 DB：执行过程中节点输出存在内存 dict 中，节点完成后才批量写入 `workflow_nodes` 表 — 减少 DB 写压力，也符合工作流引擎常见模式

### 4.2 版本约束

<!-- 无新增外部依赖，整段删除 -->

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`，每个 service 方法签名包含 `tenant_id: int` 参数
- Service `__init__` 接收 `session: AsyncSession`，**不提供默认值**
- Service 方法返回 ORM 对象或 dataclass，**不调用 `.to_dict()`**，不返回 `ApiResponse`
- Service 错误抛 `AppException` 子类（`ValidationException` 用于 cycle 检测、图解析失败）
- 引擎 `run()` 方法签名：`async def run(self, workflow_def: dict, tenant_id: int, execution_id: int) -> dict`
- 节点基类方法签名：`async def execute(self, ctx: dict) -> dict` — 所有节点方法同步且可 mock

### 4.4 已知坑

1. **SQLAlchemy `Base.metadata` 与列名 `metadata` 冲突** → 规避：在 ORM model 中避免使用 `metadata` 作为列名，若工作流定义中有 metadata 字段，用 `workflow_metadata` 或 `payload` 列名
2. **Alembic autogenerate 把 `JSONB` 写成 `JSON`、`TIMESTAMPTZ` 写成 `DateTime`** → 规避：migration 写好后手动检查并将 `sa.JSON()` 改为 `sa.JSONB().with_variant(postgresql.JSONB(), "postgresql")`，`DateTime(timezone=True)` 显式加 `timezone=True`
3. **PYTHONPATH=src 约束** → 规避：所有 import 使用 `from db.models...`、`from services...`、`from api.routers...`，**禁止** `from src.db.models...`
4. **单元测试 mock session 必须每个测试文件自己定义** → 规避：参考 `tests/unit/conftest.py` 的 `make_mock_session` 模式，在 `test_engine.py` 中定义自己独立的 `mock_db_session` fixture，不使用全局 autouse patch

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 workflow ORM models 和 migration

若 `workflow_executions` 和 `workflow_node` ORM model 尚不存在，创建它们。

在 `src/db/models/` 下（如文件不存在则新建）：

```python
# src/db/models/workflow_execution.py
from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    workflow_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
```

```python
# src/db/models/workflow_node.py
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base

class WorkflowNodeExecution(Base):
    __tablename__ = "workflow_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_executions.id"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

更新 `alembic/env.py` 添加新的 model import（若新建）。

运行 alembic autogenerate 生成 migration 文件（注意手动修正 JSON→JSONB、DateTime→TIMESTAMPTZ）。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 2: 实现节点抽象基类和 placeholder 节点

创建 `src/workflow/nodes/base.py`：

```python
# src/workflow/nodes/base.py
from abc import ABC, abstractmethod

class WorkflowNode(ABC):
    """Abstract base class for all workflow nodes."""

    def __init__(self, node_id: str, config: dict):
        self.node_id = node_id
        self.config = config

    @abstractmethod
    async def execute(self, ctx: dict) -> dict:
        """Execute the node with the given context.
        Returns a dict that will be merged into the execution context.
        """
        raise NotImplementedError
```

创建 `src/workflow/nodes/__init__.py` 实现节点注册 mapping：

```python
# src/workflow/nodes/__init__.py
from .base import WorkflowNode
from .placeholder import (
    HttpPlaceholderNode,
    ScriptPlaceholderNode,
    ConditionPlaceholderNode,
    NotifyPlaceholderNode,
)

NODE_REGISTRY: dict[str, type[WorkflowNode]] = {
    "http": HttpPlaceholderNode,
    "script": ScriptPlaceholderNode,
    "condition": ConditionPlaceholderNode,
    "notify": NotifyPlaceholderNode,
}

def load_node(node_id: str, node_type: str, config: dict) -> WorkflowNode:
    """Load a node instance by type from the registry."""
    cls = NODE_REGISTRY.get(node_type)
    if cls is None:
        raise ValidationException(f"Unknown node type: {node_type}")
    return cls(node_id=node_id, config=config)
```

创建 `src/workflow/nodes/placeholder.py` — 各 placeholder 节点返回 mock 输出，不含真实业务逻辑：

```python
# src/workflow/nodes/placeholder.py
from .base import WorkflowNode

class HttpPlaceholderNode(WorkflowNode):
    async def execute(self, ctx: dict) -> dict:
        return {"node_id": self.node_id, "status": "ok", "output": {"http_mocked": True}}

class ScriptPlaceholderNode(WorkflowNode):
    async def execute(self, ctx: dict) -> dict:
        return {"node_id": self.node_id, "status": "ok", "output": {"script_mocked": True}}

class ConditionPlaceholderNode(WorkflowNode):
    async def execute(self, ctx: dict) -> dict:
        return {"node_id": self.node_id, "status": "ok", "output": {"condition_mocked": True}}

class NotifyPlaceholderNode(WorkflowNode):
    async def execute(self, ctx: dict) -> dict:
        return {"node_id": self.node_id, "status": "ok", "output": {"notify_mocked": True}}
```

**完成判定**：`ruff check src/workflow/nodes/` → 0 errors；`PYTHONPATH=src python -c "from workflow.nodes import NODE_REGISTRY, load_node; print('OK')"` → 输出 OK

---

### Step 3: 实现 WorkflowEngine 核心类和 topological sort

创建 `src/workflow/engine.py` — 核心引擎类，实现 Kahn's algorithm topological sort、cycle 检测、顺序执行节点、将执行状态写入 DB：

```python
# src/workflow/engine.py
from datetime import datetime
from collections import defaultdict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import ValidationException
from db.models.workflow_execution import WorkflowExecution, ExecutionStatus
from db.models.workflow_node import WorkflowNodeExecution
from workflow.nodes import load_node

class WorkflowEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _topological_sort(self, nodes: list[dict], edges: list[tuple[str, str]]) -> list[str]:
        """Kahn's algorithm. Raises ValidationException on cycle."""
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}
        node_ids = {n["id"] for n in nodes}
        for n in nodes:
            in_degree[n["id"]] = 0
        for src, dst in edges:
            graph[src].append(dst)
            in_degree[dst] += 1
        queue = [n for n in node_ids if in_degree[n] == 0]
        sorted_ids: list[str] = []
        while queue:
            current = queue.pop(0)
            sorted_ids.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(sorted_ids) != len(node_ids):
            raise ValidationException("Workflow contains a cycle — execution aborted")
        return sorted_ids

    def _build_graph(workflow_def: dict) -> tuple[list[dict], list[tuple[str, str]]]:
        nodes = workflow_def.get("nodes", [])
        edges = [(e["source"], e["target"]) for e in workflow_def.get("edges", [])]
        return nodes, edges

    async def run(
        self,
        workflow_def: dict,
        tenant_id: int,
        execution_id: int,
    ) -> dict:
        nodes, edges = self._build_graph(workflow_def)
        sorted_ids = self._topological_sort(nodes, edges)
        node_map = {n["id"]: n for n in nodes}
        ctx: dict = {}
        await self.session.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .values(status=ExecutionStatus.RUNNING, started_at=datetime.utcnow())
        )
        try:
            for node_id in sorted_ids:
                node_def = node_map[node_id]
                node = load_node(node_id=node_id, node_type=node_def["type"], config=node_def.get("config", {}))
                node_record = WorkflowNodeExecution(
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    node_id=node_id,
                    node_type=node_def["type"],
                    input_data=ctx,
                    status="running",
                    started_at=datetime.utcnow(),
                )
                self.session.add(node_record)
                await self.session.flush()
                try:
                    output = await node.execute(ctx)
                    ctx[node_id] = output
                    node_record.status = "success"
                    node_record.output_data = output
                    node_record.completed_at = datetime.utcnow()
                except Exception as exc:
                    node_record.status = "failed"
                    node_record.error_message = str(exc)
                    node_record.completed_at = datetime.utcnow()
                    raise
                await self.session.commit()
            await self.session.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.id == execution_id)
                .where(WorkflowExecution.tenant_id == tenant_id)
                .values(status=ExecutionStatus.SUCCESS, completed_at=datetime.utcnow())
            )
            await self.session.commit()
            return ctx
        except Exception:
            await self.session.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.id == execution_id)
                .where(WorkflowExecution.tenant_id == tenant_id)
                .values(status=ExecutionStatus.FAILED, completed_at=datetime.utcnow())
            )
            await self.session.commit()
            raise
```

**完成判定**：`ruff check src/workflow/engine.py` → 0 errors；`PYTHONPATH=src python -c "from workflow.engine import WorkflowEngine; print('OK')"` → 输出 OK

---

### Step 4: 编写单元测试

创建 `tests/unit/test_engine.py`，覆盖：

1. **Happy path**：线性 DAG（A→B→C），验证执行顺序正确、output 正确传递
2. **Diamond DAG**：A→{B,C}→D，验证两个后继节点都收到 A 的输出
3. **Cycle detection**：图含环，验证抛出 `ValidationException`
4. **Empty workflow**：无节点，验证正常返回空 ctx

```python
# tests/unit/test_engine.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections import defaultdict
from pkg.errors.app_exceptions import ValidationException

# Inline MockSession to avoid importing real async machinery
class MockSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self._execute_result = None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def flush(self):
        for obj in self.added:
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = len(self.added)


class MockExecution:
    id = 1
    tenant_id = 1
    status = "pending"


# --- topological sort tests ---

def test_topological_sort_linear():
    from workflow.engine import WorkflowEngine
    session = MockSession()
    engine = WorkflowEngine(session)
    nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    edges = [("A", "B"), ("B", "C")]
    result = engine._topological_sort(nodes, edges)
    assert result == ["A", "B", "C"]


def test_topological_sort_diamond():
    from workflow.engine import WorkflowEngine
    session = MockSession()
    engine = WorkflowEngine(session)
    nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}]
    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
    result = engine._topological_sort(nodes, edges)
    assert result == ["A", "B", "C", "D"]


def test_topological_sort_cycle_raises():
    from workflow.engine import WorkflowEngine
    session = MockSession()
    engine = WorkflowEngine(session)
    nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    edges = [("A", "B"), ("B", "C"), ("C", "A")]
    with pytest.raises(ValidationException) as exc_info:
        engine._topological_sort(nodes, edges)
    assert "cycle" in str(exc_info.value).lower()


def test_topological_sort_empty():
    from workflow.engine import WorkflowEngine
    session = MockSession()
    engine = WorkflowEngine(session)
    result = engine._topological_sort([], [])
    assert result == []
```

（run 方法使用 patch 模拟 DB session 和节点输出，以实现端到端测试隔离）

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py -v` → 4+ passed

---

## 6. 验收

- [ ] `ruff check src/workflow/` → 0 errors
- [ ] `ruff check tests/unit/test_engine.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py -v` → ≥ 4 passed
- [ ] `alembic upgrade head` → exit 0（如 migration 文件已生成）
- [ ] `alembic downgrade -1 && alembic upgrade head` → 两次 exit 0（如涉及 migration）
- [ ] 引擎对 A→B→C DAG：`engine._topological_sort(nodes, edges) == ["A", "B", "C"]`（单元测试覆盖）
- [ ] 含环图触发 `ValidationException` 且 message 含 "cycle"（单元测试覆盖）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ORM model 列名与 Alembic autogenerate 生成结果不符（如 JSON vs JSONB），导致 migration 无法 applied | 中 | 高 | 手动修正 migration 文件，将 `sa.JSON()` 改为 JSONB，将 `DateTime` 改为 `TIMESTAMPTZ`，revert 后 re-run |
| Kahn's algorithm 在某些节点 ID 类型（int vs string 混用）下排序结果不稳定 | 低 | 中 | 节点 ID 统一为 string；`_topological_sort` 内部对 queue 使用 sorted() 保证确定性 |
| Placeholder 节点返回固定 mock 输出，后续真实节点接入时需改接口签名 | 中 | 低 | 节点 `execute(self, ctx)` 接口不变；只需在 `placeholder.py` 中替换实现为真实逻辑，接口兼容 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/workflow/ tests/unit/test_engine.py alembic/versions/*.py
git commit -m "feat(workflow): implement DAG execution engine core (#517)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(workflow): DAG execution engine core (#517)" --body "Closes #517"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/` 下已有 service 的错误处理模式（raise AppException 子类而非 return error）
- 父 issue：#73
- 前置依赖：#516（DAG 节点模型抽象层）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
