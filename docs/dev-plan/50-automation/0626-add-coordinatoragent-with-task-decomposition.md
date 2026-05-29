# CoordinatorAgent · Task decomposition and sub-agent dispatch

| 元数据 | 值 |
|---|---|
| Issue | #626 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0629-add-integration-tests-for-coordinatoragent](0629-add-integration-tests-for-coordinatoragent.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The MULTI_AGENT_DESIGN.md defines an Orchestrator/Coordinator that parses natural-language tasks, decomposes them into subtasks, dispatches subtasks to appropriate agents (code_review, test, qc, etc.), and tracks overall progress. No production implementation of this class exists in `src/agents/`. Issue #626 is the first concrete step to land a `CoordinatorAgent` backed by an `AgentRegistry`, enabling structured multi-agent orchestration within this codebase.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 agent 基础设施。
- **开发者视角**：`src/agents/coordinator.py` exports a `CoordinatorAgent` class that can be imported and instantiated with an `AgentRegistry`. Developers can call `coordinator.decompose(task_description)` to get a list of structured `SubTask` objects and `coordinator.run(subtasks)` to dispatch them to registered agents and collect results.

### 1.3 不做什么（剔除）

- [ ] Any LLM/AI model integration (prompt construction or API calls) — `CoordinatorAgent` works with structured inputs/outputs only; model invocation belongs in sub-agents registered via `AgentRegistry`.
- [ ] Persistence of task state to database — in-memory only in this phase.
- [ ] Any FastAPI router or HTTP endpoint for the coordinator.
- [ ] The `BaseAgent` abstract base is defined in this issue but not wired into any existing service/router.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_coordinator_agent.py -v` → ≥ 5 passed
- `ruff check src/agents/` → 0 errors
- `ruff check tests/unit/test_coordinator_agent.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/agents/` does not exist; no `BaseAgent` or `AgentRegistry` exists in the codebase. The only related artifacts are design documents:

- [`docs/agents/coordinator/coordinator_agent.py`](../../docs/agents/coordinator/coordinator_agent.py) — a rough script-style placeholder (not production code), ~80 lines, defines a `CoordinatorAgent` class with `parse_task`, `dispatch_to_agent`, and `run_workflow` methods using hard-coded dict returns and `subprocess.run` for dispatch.
- [`scripts/coordinator.py`](../../scripts/coordinator.py) — a standalone CLI parse helper, also not part of the `src/` tree.

Neither file provides the structured `BaseAgent` / `AgentRegistry` abstraction required by issue #626.

### 2.2 涉及文件清单

- 要改：
  - (none — this is a greenfield module, no existing production files are modified)
- 要建：
  - `src/agents/__init__.py` — exports `BaseAgent` abstract class and `AgentRegistry`
  - `src/agents/coordinator.py` — `CoordinatorAgent(BaseAgent)` with task decomposition and dispatch
  - `tests/unit/test_coordinator_agent.py` — unit tests with mocked sub-agent calls

### 2.3 缺什么

- [ ] No `BaseAgent` abstract class to inherit from — every agent needs a common interface (`name`, `execute`).
- [ ] No `AgentRegistry` to register and look up agents by name — the coordinator needs it injected.
- [ ] No structured `SubTask` / `TaskDecomposition` Pydantic models to represent decomposed work.
- [ ] No unit tests for the coordinator's decomposition and dispatch logic.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/agents/__init__.py` | Exports `BaseAgent` (ABC) and `AgentRegistry`; serves as the `src/agents/` package entry point |
| `src/agents/coordinator.py` | `CoordinatorAgent(BaseAgent)` — parses natural-language task, decomposes into `SubTask` list, dispatches via `AgentRegistry`, tracks progress |
| `tests/unit/test_coordinator_agent.py` | Unit tests: happy path, boundary (empty task), error (unknown agent), all with mocked `AgentRegistry` |

### 3.2 修改文件

(none — issue scope is strictly `src/agents/coordinator.py` + its test file)

### 3.3 新增能力

- **Abstract class**：`BaseAgent` in `src/agents/__init__.py` — defines `name: str` property and `async execute(self, task: dict) -> dict` abstract method
- **Class**：`AgentRegistry` in `src/agents/__init__.py` — `register(agent)`, `get(name) -> BaseAgent`, `list_agents() -> list[str]`; raises `KeyError` for unknown agent
- **Class**：`CoordinatorAgent(BaseAgent)` in `src/agents/coordinator.py` — `async decompose(task_description: str) -> TaskDecomposition` and `async run(decomposition: TaskDecomposition) -> WorkflowResult`
- **Pydantic models**：`SubTask`, `TaskDecomposition`, `WorkflowResult` in `src/agents/coordinator.py`
- **Test fixture**：`mock_agent_registry()` in `tests/unit/test_coordinator_agent.py` using `MagicMock` / `AsyncMock`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Extend `BaseAgent` (ABC) rather than a plain Protocol or concrete class** — enforces that every agent has `name` and `execute`, making `AgentRegistry` safe to dispatch to without `hasattr` checks.
- **Pydantic models for task/subtask rather than raw dicts** — enables runtime validation and IDE autocompletion; avoids silent typos in field names.
- **`AgentRegistry` injected via constructor (not a global singleton)** — makes testing straightforward (pass a mock) and avoids implicit global state.

### 4.2 版本约束

(none — no new external dependencies)

### 4.3 兼容性约束

- All `async def` methods; caller must `await` them.
- `AgentRegistry.get(name)` raises `KeyError` if agent not found — callers handle it explicitly.
- `PYTHONPATH=src` is required for imports (`from agents.coordinator import CoordinatorAgent` resolves as `from src.agents.coordinator import ...`).
- Do not use `metadata` as a field name in any Pydantic model inside `src/agents/` (not reserved here but follows the repo-wide convention against `Base.metadata` collision).

### 4.4 已知坑

1. **PYTHONPATH must include `src`** → `ruff check src/agents/` and the test command will fail with `ModuleNotFoundError` if PYTHONPATH is not set; always prefix commands with `PYTHONPATH=src`.
2. **Mock `AgentRegistry` returning mock agents must have `execute` as an `AsyncMock`** → if a test accidentally sets `execute` as a plain `MagicMock`, `await agent.execute(...)` will return a coroutine object instead of the result; always use `AsyncMock` for the `execute` method on registered agent mocks.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/agents/` package with `BaseAgent` and `AgentRegistry`

Create `src/agents/__init__.py`. Define `BaseAgent` as an `ABC` with `name: str` property and `async execute(self, task: dict) -> dict` abstract method. Define `AgentRegistry` as a plain class with `register(agent: BaseAgent)`, `get(name: str) -> BaseAgent` (raises `KeyError` if not found), and `list_agents() -> list[str]`.

```python
# src/agents/__init__.py
from abc import ABC, abstractmethod
from typing import ClassVar


class BaseAgent(ABC):
    """Abstract base for all agents in the system."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""
        ...

    @abstractmethod
    async def execute(self, task: dict) -> dict:
        """Execute the given task and return a result dict."""
        ...


class AgentRegistry:
    """Central registry for all agents. Injected into CoordinatorAgent."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"No agent registered with name: {name}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())
```

**完成判定**：`PYTHONPATH=src ruff check src/agents/__init__.py` → 0 errors

---

### Step 2: Define Pydantic models for tasks and subtasks

Add to `src/agents/coordinator.py` (the file will be created in Step 3). Define three Pydantic models:

- `SubTask(id: str, agent_name: str, description: str, status: str = "pending", result: dict | None = None)` — one atomic unit of work.
- `TaskDecomposition(task_id: str, original_description: str, subtasks: list[SubTask])` — the output of decomposition.
- `WorkflowResult(task_id: str, completed: list[SubTask], failed: list[SubTask])` — the outcome of running a decomposition.

```python
# src/agents/coordinator.py  (Pydantic models section)
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    id: str
    agent_name: str
    description: str
    status: str = "pending"
    result: dict | None = None


class TaskDecomposition(BaseModel):
    task_id: str
    original_description: str
    subtasks: list[SubTask]


class WorkflowResult(BaseModel):
    task_id: str
    completed: list[SubTask] = Field(default_factory=list)
    failed: list[SubTask] = Field(default_factory=list)
```

**完成判定**：`PYTHONPATH=src python -c "from agents.coordinator import SubTask, TaskDecomposition, WorkflowResult; print('OK')"` → OK (no output means success)

---

### Step 3: Implement `CoordinatorAgent` class

Write the full `CoordinatorAgent` class in `src/agents/coordinator.py`. It extends `BaseAgent`, takes `AgentRegistry` in `__init__`, and provides:

- `name` property returning `"coordinator"`
- `async execute(self, task: dict) -> dict` — top-level entry point; calls `decompose` then `run`
- `async decompose(self, task_description: str) -> TaskDecomposition` — parses the natural-language description and returns a `TaskDecomposition`. For this phase, a rule-based parser (keyword matching) is used: `"test"` → agent `"test_agent"`, `"review"` / `"code"` → `"code_review_agent"`, `"qc"` / `"quality"` → `"qc_agent"`. Unknown keywords → `"implement_agent"`. Task ID is generated with `uuid.uuid4().hex[:8]`.
- `async run(self, decomposition: TaskDecomposition) -> WorkflowResult` — iterates `decomposition.subtasks` in order, calls `registry.get(agent_name).execute(subtask.to_dict())`, catches `KeyError` for unknown agent (appends to `failed`), catches any `Exception` (appends to `failed` with error in `result`), and appends successful ones to `completed`. Returns a `WorkflowResult`.

Import `BaseAgent` and `AgentRegistry` from `agents` (relative: `from agents import BaseAgent, AgentRegistry`).

```python
# src/agents/coordinator.py
import uuid
from agents import AgentRegistry, BaseAgent


class CoordinatorAgent(BaseAgent):
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    @property
    def name(self) -> str:
        return "coordinator"

    async def execute(self, task: dict) -> dict:
        decomposition = await self.decompose(task["description"])
        result = await self.run(decomposition)
        return result.model_dump()

    async def decompose(self, task_description: str) -> TaskDecomposition:
        task_id = uuid.uuid4().hex[:8]
        keywords = {("test",): "test_agent", ("review", "code", "review"): "code_review_agent", ("qc", "quality"): "qc_agent"}
        subtasks = []
        for i, keyword_group in enumerate(keywords):
            if any(kw in task_description.lower() for kw in keyword_group):
                subtasks.append(SubTask(id=f"{task_id}-{i}", agent_name=keyword_group[0] + "_agent", description=task_description))
        if not subtasks:
            subtasks.append(SubTask(id=f"{task_id}-0", agent_name="implement_agent", description=task_description))
        return TaskDecomposition(task_id=task_id, original_description=task_description, subtasks=subtasks)

    async def run(self, decomposition: TaskDecomposition) -> WorkflowResult:
        completed, failed = [], []
        for st in decomposition.subtasks:
            try:
                agent = self._registry.get(st.agent_name)
                st.result = await agent.execute(st.model_dump())
                st.status = "completed"
                completed.append(st)
            except KeyError:
                st.status = "failed"
                st.result = {"error": f"Unknown agent: {st.agent_name}"}
                failed.append(st)
            except Exception as exc:
                st.status = "failed"
                st.result = {"error": str(exc)}
                failed.append(st)
        return WorkflowResult(task_id=decomposition.task_id, completed=completed, failed=failed)
```

**完成判定**：`PYTHONPATH=src ruff check src/agents/coordinator.py` → 0 errors

---

### Step 4: Write unit tests

Create `tests/unit/test_coordinator_agent.py`. Use `pytest` with `pytest.mark.asyncio`. Provide a `mock_agent_registry(agents: list[BaseAgent]) -> AgentRegistry` fixture that returns a real `AgentRegistry` populated with the given agents. For each test, register agents whose `execute` is an `AsyncMock` returning `{"status": "ok"}`.

Test cases:

1. **`test_decompose_assigns_correct_agent`** — call `decompose("write tests for login")`, assert the single subtask has `agent_name == "test_agent"` and `status == "pending"`.
2. **`test_decompose_code_review`** — decompose `"review the auth module"`, assert agent is `"code_review_agent"`.
3. **`test_run_all_succeed`** — mock registry with two agents that both return `{"ok": true}`; call `run()`; assert `WorkflowResult.completed` has 2 items, `failed` is empty, each subtask `status == "completed"`.
4. **`test_run_unknown_agent`** — register no agents; call `run()` on a decomposition with one subtask targeting `"nonexistent_agent"`; assert that subtask is in `failed` and `result["error"]` mentions the agent name.
5. **`test_run_exception`** — register an agent whose `execute` raises `RuntimeError("boom")`; assert the subtask is in `failed` and `result["error"] == "boom"`.
6. **`test_execute_integration`** — call `execute({"description": "review and test"})`; assert returned dict has two subtasks and no exceptions propagate.

```python
# tests/unit/test_coordinator_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents import AgentRegistry, BaseAgent
from agents.coordinator import CoordinatorAgent, TaskDecomposition, SubTask


def mock_agent_registry(agents: list[BaseAgent]) -> AgentRegistry:
    reg = AgentRegistry()
    for a in agents:
        reg.register(a)
    return reg


class DummyAgent(BaseAgent):
    def __init__(self, agent_name: str, result: dict) -> None:
        self._name = agent_name
        self._execute = AsyncMock(return_value=result)

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, task: dict) -> dict:
        return await self._execute(task)


@pytest.mark.asyncio
async def test_decompose_assigns_test_agent():
    reg = mock_agent_registry([])
    coord = CoordinatorAgent(reg)
    result = await coord.decompose("write tests for login")
    assert len(result.subtasks) == 1
    assert result.subtasks[0].agent_name == "test_agent"
    assert result.subtasks[0].status == "pending"


@pytest.mark.asyncio
async def test_decompose_assigns_code_review_agent():
    reg = mock_agent_registry([])
    coord = CoordinatorAgent(reg)
    result = await coord.decompose("review the auth module")
    assert result.subtasks[0].agent_name == "code_review_agent"


@pytest.mark.asyncio
async def test_run_all_succeed():
    a1 = DummyAgent("test_agent", {"ok": True})
    a2 = DummyAgent("code_review_agent", {"ok": True})
    reg = mock_agent_registry([a1, a2])
    coord = CoordinatorAgent(reg)
    decomposition = TaskDecomposition(
        task_id="t01",
        original_description="test and review",
        subtasks=[SubTask(id="t01-0", agent_name="test_agent", description="test"), SubTask(id="t01-1", agent_name="code_review_agent", description="review")],
    )
    result = await coord.run(decomposition)
    assert len(result.completed) == 2
    assert len(result.failed) == 0


@pytest.mark.asyncio
async def test_run_unknown_agent():
    reg = mock_agent_registry([])
    coord = CoordinatorAgent(reg)
    decomposition = TaskDecomposition(task_id="t02", original_description="do something", subtasks=[SubTask(id="t02-0", agent_name="ghost_agent", description="ghost")])
    result = await coord.run(decomposition)
    assert len(result.failed) == 1
    assert "ghost_agent" in result.failed[0].result["error"]


@pytest.mark.asyncio
async def test_run_exception():
    broken = DummyAgent("broken_agent", {})
    broken.execute = AsyncMock(side_effect=RuntimeError("boom"))
    reg = mock_agent_registry([broken])
    coord = CoordinatorAgent(reg)
    decomposition = TaskDecomposition(task_id="t03", original_description="break", subtasks=[SubTask(id="t03-0", agent_name="broken_agent", description="break")])
    result = await coord.run(decomposition)
    assert len(result.failed) == 1
    assert result.failed[0].result["error"] == "boom"


@pytest.mark.asyncio
async def test_execute_integration():
    a = DummyAgent("code_review_agent", {"status": "ok"})
    reg = mock_agent_registry([a])
    coord = CoordinatorAgent(reg)
    outcome = await coord.execute({"description": "review and test"})
    assert outcome["task_id"] is not None
    assert len(outcome["completed"]) == 2
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_coordinator_agent.py -v` → 6 passed

---

## 6. 验收

- [ ] `ruff check src/agents/` → 0 errors
- [ ] `ruff check tests/unit/test_coordinator_agent.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from agents.coordinator import CoordinatorAgent; print('import OK')"` → import OK (silent on success)
- [ ] `PYTHONPATH=src pytest tests/unit/test_coordinator_agent.py -v` → 6 passed
- [ ] `PYTHONPATH=src ruff format --check src/agents/` → exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Keyword-based decomposition is too brittle and misroutes real tasks | 中 | 中 | The decomposition logic is isolated to `decompose()`; replace with a more sophisticated parser (regex, LLM call, or config table) without touching `run()` or the test file |
| `AgentRegistry` is a new shared dependency that later agents also depend on — if its API changes, all agents break | 低 | 中 | Pin the registry API (add methods only, never remove/rename); add a version sentinel if needed |
| `AsyncMock` used incorrectly in tests leading to false positives | 低 | 高 | All agent mock `execute` methods must be `AsyncMock`; Step 4 known坑 documents this explicitly |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/agents/__init__.py src/agents/coordinator.py tests/unit/test_coordinator_agent.py
git commit -m "feat(agents): add CoordinatorAgent with task decomposition and AgentRegistry"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(agents): add CoordinatorAgent (#626)" --body "Closes #626"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`docs/agents/coordinator/coordinator_agent.py`](../../docs/agents/coordinator/coordinator_agent.py) — design doc / placeholder this production module replaces
- 同类参考实现：[`scripts/coordinator.py`](../../scripts/coordinator.py) — existing CLI parse helper (not part of `src/agents/`)
- 父 issue / 关联：#41
- 依赖 issue / 关联：#625
