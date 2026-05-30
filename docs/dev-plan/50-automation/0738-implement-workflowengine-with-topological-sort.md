# WorkflowEngine · Implement topological sort engine for workflow execution

| 元数据 | 值 |
|---|---|
| Issue | #738 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [WorkflowEngine skeleton](0739-write-test-engine-py-unit-tests.md) |
| 启用后赋能 | TBD - 待补充：依赖 #737 的后续模块（如 router/actor） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #517 defines a multi-tenant workflow execution engine as the CRM's long-running process orchestrator. Issue #738 provides the core execution logic: Kahn's algorithm topological sort detects cyclic DAGs before running, `_build_graph()` constructs the adjacency representation, and `run()` persists `workflow_executions` + `workflow_nodes` rows per node. Without this, the workflow router has no backing service — nothing can actually execute a DAG.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 service 模块，供 API router 调用。
- **开发者视角**：`WorkflowEngine(session: AsyncSession)` is a first-class CRM service. Callers inject `AsyncSession` via `Depends(get_db)`, invoke `await engine.run(workflow_def, tenant_id, execution_id)`, and get `AppException(ValidationException)` on cyclic DAG before any DB writes.

### 1.3 不做什么（剔除）

- [ ] Persistence of `workflow_executions` row itself (caller is responsible for inserting the execution row before calling `run()`)
- [ ] Node execution / state machine logic (stubbed as future work in #517)
- [ ] API router for workflows (belongs to a separate issue)

### 1.4 关键 KPI

- `ruff check src/workflow/engine.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_workflow_engine.py -v` → ≥ 5 passed (cycle detection + topological sort + run smoke)
- Kahn's algorithm raises `ValidationException("Cyclic dependency detected")` on input containing a cycle

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/workflow/engine.py` 是否已存在 — 若存在请补充文件结构和 `WorkflowEngine` 类签名

```{python}:1:src/workflow/engine.py
# TBD — file may already be scaffolded by #737
from sqlalchemy.ext.asyncio import AsyncSession

class WorkflowEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
```

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/workflow/engine.py` — 实现 `_topological_sort`, `_build_graph`, `run`
  - TBD - 待验证：`tests/unit/test_workflow_engine.py` — 单元测试（依赖 #737 scaffold）
- 要建：
  - `src/db/models/workflow_execution.py` — `WorkflowExecution` ORM model（如果不存在）
  - `src/db/models/workflow_node.py` — `WorkflowNode` ORM model（如果不存在）
  - `alembic/versions/<id>_create_workflow_tables.py` — 迁移（如果表不存在）

### 2.3 缺什么

- [ ] Kahn's algorithm `_topological_sort` that raises `ValidationException` on cycle
- [ ] `_build_graph` adjacency list from `workflow_def` dict/list structure
- [ ] `run` method that iterates nodes in topologically-sorted order and inserts `workflow_nodes` rows
- [ ] `WorkflowExecution` and `WorkflowNode` ORM models with correct `tenant_id` columns
- [ ] Full unit test suite covering: happy path, cycle detection, empty DAG, single-node DAG

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/workflow/engine.py` | `WorkflowEngine` service class with topological sort + run |
| `src/db/models/workflow_execution.py` | ORM model for `workflow_executions` table (if not already created by #737) |
| `src/db/models/workflow_node.py` | ORM model for `workflow_nodes` table (if not already created by #737) |
| `alembic/versions/<id>_create_workflow_tables.py` | Migration creating both tables with `tenant_id` and indexes (if not already created) |
| `tests/unit/test_workflow_engine.py` | Unit tests: topological sort, cycle detection, run smoke |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/db/models/__init__.py` 或 `src/db/models/workflow.py` | 注册 WorkflowExecution / WorkflowNode models |
| TBD - 待验证：`alembic/env.py` | import new models so autogenerate sees them |

### 3.3 新增能力

- **Service class**：`WorkflowEngine(session: AsyncSession)` — no default session, raises `AppException`
- **Service method**：`WorkflowEngine._topological_sort(self, graph: dict[str, list[str]]) -> list[str]` — Kahn's algorithm, raises `ValidationException("Cyclic dependency detected")` on cycle
- **Service method**：`WorkflowEngine._build_graph(self, workflow_def: dict) -> dict[str, list[str]]` — converts `workflow_def["nodes"]` + edges to adjacency list
- **Service method**：`async WorkflowEngine.run(self, workflow_def: dict, tenant_id: int, execution_id: int) -> list[WorkflowNode]` — updates `workflow_executions`, inserts `workflow_nodes` per node in sorted order
- **ORM model**：`WorkflowExecution` in `src/db/models/workflow_execution.py` (if new)
- **ORM model**：`WorkflowNode` in `src/db/models/workflow_node.py` (if new)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Kahn's algorithm 不选 DFS post-order**：DFS requires recursion or explicit stack; Kahn's is iterative (async-safe, no Python call-stack risk for large DAGs) and naturally detects cycles by checking remaining in-degree > 0 nodes after drain.
- **Cycle detection inline in Kahn's**：No separate cycle-check pass — Kahn's naturally leaves nodes with remaining in-degree > 0 after queue empties, which signals a cycle. Avoids O(V+E) extra pass.
- **workflow_def as dict, not Pydantic model**：Defers schema design to #517 follow-up; accepts a plain dict from the router's JSON body so the schema can evolve independently.

### 4.2 版本约束

<!-- 无新增外部依赖 -->

### 4.3 兼容性约束

- `WorkflowEngine.__init__(self, session: AsyncSession)` — **no default**, caller must provide session
- All DB queries must `WHERE tenant_id = :tenant_id`
- `run()` returns `list[WorkflowNode]` ORM objects; does **not** call `.to_dict()`
- On cycle: raise `ValidationException("Cyclic dependency detected")` — do **not** return an error dict
- `WorkflowNode` column named `event_metadata` or `payload`, **not** `metadata` (conflicts with `Base.metadata`)

### 4.4 已知坑

1. **SQLAlchemy `metadata` column name conflict** → ORM column must be named `event_metadata` or `payload`, never `metadata`
2. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()`** → After autogenerate, manually replace `JSON()` with `JSONB()` for columns that need JSONB performance
3. **Alembic drops `timezone=True` on DateTime columns** → After autogenerate, verify `DateTime(timezone=True)` is used for all timestamp columns
4. **Async session injection** → Routers must use `session: AsyncSession = Depends(get_db)`, never `async with get_db() as session:`

---

## 5. 实现步骤（按顺序）

### Step 1: Verify or create ORM models `WorkflowExecution` and `WorkflowNode`

If `src/db/models/workflow_execution.py` and `src/db/models/workflow_node.py` do not exist (check with grep), create them.

`src/db/models/workflow_execution.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    triggered_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`src/db/models/workflow_node.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    execution_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    node_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Register both in `src/db/models/__init__.py` (or the models module) and import them in `alembic/env.py`.

If the tables already exist (migrated by a sibling issue), skip this step.

**完成判定**：`PYTHONPATH=src ruff check src/db/models/workflow_execution.py src/db/models/workflow_node.py` → 0 errors

---

### Step 2: Generate alembic migration for workflow tables

Only if new tables are needed (not yet migrated):

```bash
# Start a clean alembic_dev database
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "create workflow_executions and workflow_nodes tables"
```

After autogenerate, edit the migration:
- Replace `sa.JSON()` with `sa.JSONB()` for the `payload` column
- Verify `DateTime(timezone=True)` on `started_at`, `completed_at` columns

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0

---

### Step 3: Implement `WorkflowEngine._build_graph`

Add to `src/workflow/engine.py`:

```python
from typing import TypedDict

class WorkflowEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _build_graph(self, workflow_def: dict) -> dict[str, list[str]]:
        nodes: list[str] = [n["key"] for n in workflow_def.get("nodes", [])]
        edges: list[tuple[str, str]] = workflow_def.get("edges", [])

        graph: dict[str, list[str]] = {n: [] for n in nodes}
        for src, dst in edges:
            if src in graph:
                graph[src].append(dst)
        return graph
```

**完成判定**：`PYTHONPATH=src ruff check src/workflow/engine.py` → 0 errors

---

### Step 4: Implement `WorkflowEngine._topological_sort` (Kahn's algorithm)

Add to `src/workflow/engine.py`:

```python
from collections import deque
from pkg.errors.app_exceptions import ValidationException

class WorkflowEngine:
    def _topological_sort(self, graph: dict[str, list[str]]) -> list[str]:
        # Compute in-degree for each node
        in_degree: dict[str, int] = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1

        # Kahn's algorithm
        queue: deque[str] = deque([n for n, d in in_degree.items() if d == 0])
        sorted_order: list[str] = []

        while queue:
            node = queue.popleft()
            sorted_order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(graph):
            raise ValidationException("Cyclic dependency detected")

        return sorted_order
```

**完成判定**：`PYTHONPATH=src ruff check src/workflow/engine.py` → 0 errors

---

### Step 5: Implement `async WorkflowEngine.run`

Add to `src/workflow/engine.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import select, update
from db.models.workflow_execution import WorkflowExecution
from db.models.workflow_node import WorkflowNode

class WorkflowEngine:
    async def run(
        self,
        workflow_def: dict,
        tenant_id: int,
        execution_id: int,
    ) -> list[WorkflowNode]:
        graph = self._build_graph(workflow_def)
        sorted_keys = self._topological_sort(graph)

        now = datetime.now(timezone.utc)

        # Update execution status to running
        await self.session.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .values(status="running", started_at=now)
        )

        node_records: list[WorkflowNode] = []
        for key in sorted_keys:
            node = WorkflowNode(
                tenant_id=tenant_id,
                execution_id=execution_id,
                node_key=key,
                status="pending",
                started_at=now,
            )
            self.session.add(node)
            node_records.append(node)

        await self.session.flush()
        return node_records
```

**完成判定**：`PYTHONPATH=src ruff check src/workflow/engine.py` → 0 errors

---

### Step 6: Write unit tests covering topological sort, cycle detection, and run smoke

Create `tests/unit/test_workflow_engine.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from workflow.engine import WorkflowEngine
from pkg.errors.app_exceptions import ValidationException


class TestTopologicalSort:
    def _engine(self):
        mock_session = MagicMock()
        return WorkflowEngine(mock_session)

    def test_linear_chain_returns_sorted_order(self):
        engine = self._engine()
        graph = {"a": ["b"], "b": ["c"], "c": []}
        result = engine._topological_sort(graph)
        assert result == ["a", "b", "c"]

    def test_diamond_returns_any_valid_topological_order(self):
        engine = self._engine()
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        result = engine._topological_sort(graph)
        assert result[0] == "a"
        assert result[-1] == "d"
        assert set(result) == {"a", "b", "c", "d"}

    def test_raises_validation_exception_on_cycle(self):
        engine = self._engine()
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        with pytest.raises(ValidationException) as exc_info:
            engine._topological_sort(graph)
        assert "Cyclic dependency" in str(exc_info.value)

    def test_empty_graph_returns_empty(self):
        engine = self._engine()
        assert engine._topological_sort({}) == []

    def test_single_node_no_edges(self):
        engine = self._engine()
        assert engine._topological_sort({"a": []}) == ["a"]


class TestBuildGraph:
    def _engine(self):
        return WorkflowEngine(MagicMock())

    def test_constructs_adjacency_from_nodes_and_edges(self):
        engine = self._engine()
        wf_def = {
            "nodes": [{"key": "n1"}, {"key": "n2"}, {"key": "n3"}],
            "edges": [("n1", "n2"), ("n2", "n3")],
        }
        graph = engine._build_graph(wf_def)
        assert graph == {"n1": ["n2"], "n2": ["n3"], "n3": []}


class TestRun:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_run_updates_execution_and_inserts_nodes(self, mock_session):
        engine = WorkflowEngine(mock_session)
        wf_def = {
            "nodes": [{"key": "start"}, {"key": "end"}],
            "edges": [("start", "end")],
        }
        nodes = await engine.run(wf_def, tenant_id=1, execution_id=42)
        assert mock_session.execute.called
        assert len(nodes) == 2
        node_keys = [n.node_key for n in nodes]
        assert "start" in node_keys
        assert "end" in node_keys
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_engine.py -v` → ≥ 5 passed

---

## 6. 验收

- [ ] `ruff check src/workflow/engine.py src/db/models/workflow_execution.py src/db/models/workflow_node.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_engine.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_workflow_integration.py -v` → 全 passed（如 integration 测试存在且 #737 已完成）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及新 migration）
- [ ] Kahn's algorithm: `engine._topological_sort({"a":["b"],"b":["c"],"c":[]})` returns `["a","b","c"]`; `engine._topological_sort({"a":["b"],"b":["c"],"c":["a"]})` raises `ValidationException`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ORM models collide with existing table schema from #737 | 低 | 中 | 在 `alembic/env.py` 中确认所有 workflow model 已被 import；若有冲突迁移，调整迁移而非改 model |
| Cycle detection false positive on valid DAG with multiple entry nodes | 低 | 中 | Unit test `test_diamond_returns_any_valid_topological_order` 覆盖并验证 |
| `ValidationException` message diverges from caller expectations | 低 | 中 | 统一使用 `"Cyclic dependency detected"`；在 router 层统一处理消息展示 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/workflow/engine.py src/db/models/workflow_execution.py src/db/models/workflow_node.py tests/unit/test_workflow_engine.py
git commit -m "feat(workflow): implement WorkflowEngine with Kahn topological sort"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(workflow): implement WorkflowEngine with topological sort (#738)" --body "Closes #738"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/customer_service.py` — 现有 CRM service 模式参考
- 父 issue / 关联：#517, #737

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-30 | 创建 | TBD |
