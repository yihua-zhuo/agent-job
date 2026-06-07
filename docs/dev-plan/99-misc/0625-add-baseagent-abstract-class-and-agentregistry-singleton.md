# agents ·抽象 BaseAgent 类与单例 AgentRegistry

| 元数据 | 值 |
|---|---|
| Issue | #625 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | (各 AI agent 功能板块) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM system is evolving toward AI-augmented workflows that invoke LLM providers against structured data. Without a shared abstraction layer, each new agent duplicates dependency-injection patterns, loses discoverability, and complicates unit testing. An abstract `BaseAgent` + singleton `AgentRegistry` establishes a consistent contract that all current and future agents must implement, enabling decorator-based registration, centralized lookup, and type-safe dependency injection from day one.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层架构。
- **开发者视角**：`from src.agents.registry import registry; agent = registry.get("base")` returns the registered `BaseAgent` instance. `registry.list_agents()` returns `["base"]`. Any new agent can inherit `BaseAgent`, decorate itself with `@registry.register("my_agent")`, and immediately benefit from discoverability and uniform `run()` semantics。

### 1.3 不做什么（剔除）

- [ ] No LLM invocation logic in this step — `run()` raises `NotImplementedError`.
- [ ] No service or API layer wiring — no router changes, no DB migrations.
- [ ] No persistence of agent instances — `AgentRegistry` holds in-memory singletons only.

### 1.4 关键 KPI

- `ruff check src/agents/` → 0 errors — TBD - 待验证
- `PYTHONPATH=src pytest tests/unit/test_base_agent.py -v` → 4 passed — TBD - 待验证
- `PYTHONPATH=src pytest tests/unit/test_agent_registry.py -v` → 5 passed — TBD - 待验证
- `src/agents/base.py` and `src/agents/registry.py` exist with correct public APIs

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

`src/agents/` does not yet exist. The directory will be created as part of this issue. There is no existing agent infrastructure to extend.

### 2.2 涉及文件清单

- 要改：
  - (none)
- 要建：
  - `src/agents/base.py` — `BaseAgent` abstract class
  - `src/agents/registry.py` — `AgentRegistry` singleton with `@register` decorator
  - `tests/unit/test_base_agent.py` — unit tests for `BaseAgent`
  - `tests/unit/test_agent_registry.py` — unit tests for `AgentRegistry`

### 2.3 缺什么

- [ ] No abstract agent base class with typed `run()` signature and dependency injection points
- [ ] No centralized registry for agent discovery and lookup
- [ ] No `@register` decorator for declarative agent registration
- [ ] No singleton guarantee in registry — current design risk of duplicate instances
- [ ] No unit tests covering agent base class or registry behavior

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/agents/base.py` | Abstract `BaseAgent` class with `llm`/`db` constructor params and abstract `run(task: str) -> Dict` |
| `src/agents/registry.py` | Singleton `AgentRegistry` with `@register(name)` decorator, `get(name)`, and `list_agents()` |
| `tests/unit/test_base_agent.py` | Unit tests: instantiation, abstract method raises `NotImplementedError`, type hints |
| `tests/unit/test_agent_registry.py` | Unit tests: singleton uniqueness, `@register` decorator, `get`, `list_agents`, error on unknown name |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| (none) | No existing files are modified |

### 3.3 新增能力

- **Abstract class**：`BaseAgent(ABC)` in `src/agents/base.py` — constructor accepts `llm: Any` and `db: AsyncSession`; defines `@abstractmethod run(task: str) -> Dict`
- **Singleton**：`AgentRegistry` in `src/agents/registry.py` — module-level singleton; `@register(name)` class decorator; `get(name: str) -> BaseAgent`; `list_agents() -> list[str]`
- **Registration**：module-level `registry = AgentRegistry()` instance; `BaseAgent` subclasses in `src/agents/` auto-register via decorator

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Singleton `AgentRegistry` as module-level object, not a class with `__new__` singleton trick** — because a module-level instance is simpler to inspect in tests (no `is` comparison needed to prove uniqueness) and works naturally with Python's import caching.
- **`@register(name)` as a class decorator on `BaseAgent` subclasses** — declarative and scannable; alternative of a `register()` call in `__init__` is error-prone if subclasses forget to call `super().__init__`.
- **`llm: Any` type for LLM dependency instead of a protocol** — to avoid introducing an extra abstraction layer before the first concrete agent exists; revisit with a protocol once concrete LLM backends are known.

### 4.2 版本约束

(no new dependencies)

### 4.3 兼容性约束

- All SQL queries must `WHERE tenant_id = :tenant_id` even though `db` is passed as a generic `AsyncSession` here — the contract is inherited by future concrete agents.
- Service error conventions: concrete agents should raise `AppException` subclasses, not return error dicts, to be consistent with the service layer.

### 4.4 已知坑

1. **`ABC` abstract method not actually abstract if subclass does not define `run`** → Python raises `TypeError` only at instantiation time. Mitigation: unit tests verify the `TypeError` is raised for unregistered subclasses.
2. **Import cycle if `BaseAgent` ever imports from `registry`** → mitigation: keep `base.py` and `registry.py` independently importable; `BaseAgent` does not import `AgentRegistry`.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/agents/` directory and `src/agents/base.py`

Create the directory and the abstract `BaseAgent` class file.

操作：
- a) Create directory `src/agents/`
- b) Create `src/agents/base.py` with the following content — `ABC`-derived class, `__init__` storing `llm`/`db`, `@abstractmethod run` with typed signature

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

class BaseAgent(ABC):
    def __init__(self, llm: Any, db: AsyncSession) -> None:
        self.llm = llm
        self.db = db

    @abstractmethod
    async def run(self, task: str) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement run()")
```

**完成判定**：`ls src/agents/base.py` exists / `ruff check src/agents/base.py` → 0 errors

### Step 2: Create `src/agents/registry.py` with `AgentRegistry`

Create the singleton registry with decorator, `get`, and `list_agents`.

操作：
- a) Create `src/agents/registry.py`
- b) Define `AgentRegistry` class with `_agents: Dict[str, type]` internal dict
- c) Add `@register(name)` class/method decorator that stores the class under `name`
- d) Add `get(name: str) -> BaseAgent` method that instantiates and returns
- e) Add `list_agents() -> list[str]` method
- f) Create module-level `registry = AgentRegistry()` instance

```python
from typing import Dict, List, Type
from src.agents.base import BaseAgent

class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, Type[BaseAgent]] = {}

    def register(self, name: str):
        def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
            self._agents[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not registered")
        cls = self._agents[name]
        raise TypeError("AgentRegistry.get() requires llm and db args — use get_with_deps()")
        # stub; real implementation fills in llm/db from outer scope or caller
    def list_agents(self) -> List[str]:
        return list(self._agents.keys())

registry = AgentRegistry()
```

Note: refine `get()` to accept `(name, llm, db)` args so callers can instantiate with dependencies in one call.

**完成判定**：`ls src/agents/registry.py` exists / `ruff check src/agents/registry.py` → 0 errors

### Step 3: Register `BaseAgent` with the registry

Add `@registry.register("base")` decorator to `BaseAgent` in `src/agents/base.py`.

操作：
- a) In `src/agents/base.py`, import `registry` from `src.agents.registry`
- b) Apply `@registry.register("base")` decorator above `class BaseAgent(ABC)`

**完成判定**：`PYTHONPATH=src python -c "from src.agents.registry import registry; assert 'base' in registry.list_agents()"` → exit 0

### Step 4: Write unit tests for `BaseAgent` in `tests/unit/test_base_agent.py`

操作：
- a) Create `tests/unit/test_base_agent.py`
- b) Test 1: `BaseAgent` cannot be instantiated directly (is abstract)
- c) Test 2: subclass without `run()` raises `TypeError` at instantiation
- d) Test 3: subclass with `run()`returns expected dict (mock `llm`/`db`)
- e) Test 4: `run()` re-raises `NotImplementedError` when called on concrete stub
```python
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.base import BaseAgent

class DummyAgent(BaseAgent):
    async def run(self, task: str):
        return {"task": task, "status": "done"}

class NoRunAgent(BaseAgent):
    pass

@pytest.mark.asyncio
async def test_base_agent_is_abstract():
    with pytest.raises(TypeError):
        BaseAgent(llm=None, db=None)

@pytest.mark.asyncio
async def test_subclass_without_run_raises():
    with pytest.raises(TypeError):
        NoRunAgent(llm=None, db=None)

@pytest.mark.asyncio
async def test_subclass_run_returns_dict():
    agent = DummyAgent(llm=None, db=None)
    result = await agent.run("test task")
    assert result == {"task": "test task", "status": "done"}

@pytest.mark.asyncio
async def test_llm_and_db_stored():
    llm = object()
    db = object()
    agent = DummyAgent(llm=llm, db=db)
    assert agent.llm is llm
    assert agent.db is db
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_base_agent.py -v` → `4 passed`

### Step 5: Write unit tests for `AgentRegistry` in `tests/unit/test_agent_registry.py`

操作：
- a) Create `tests/unit/test_agent_registry.py`
- b) Test1: `registry` is same object on repeated imports (singleton)
- c) Test 2: `register` decorator stores class under given name
- d) Test 3: `get` raises `KeyError` for unknown agent
- e) Test 4: `get` returns instance with llm/db passed through
- e) Test 5: `list_agents` returns all registered names including "base"

```python
import pytest
from src.agents.registry import AgentRegistry, registry
from src.agents.base import BaseAgent

class TestAgent(BaseAgent):
    async def run(self, task: str):
        return {"agent": "test"}

@pytest.mark.asyncio
async def test_singleton_same_object():
    from src.agents import registry as r2
    assert registry is r2

@pytest.mark.asyncio
async def test_register_decorator():
    local_registry = AgentRegistry()
    @local_registry.register("my_agent")
    class MyAgent(BaseAgent):
        async def run(self, task: str):
            return {}
    assert "my_agent" in local_registry.list_agents()

@pytest.mark.asyncio
async def test_get_unknown_raises():
    with pytest.raises(KeyError):
        registry.get("nonexistent_agent_xyz")

@pytest.mark.asyncio
async def test_get_returns_instance():
    llm, db = object(), object()
    agent = registry.get("base", llm=llm, db=db)
    assert isinstance(agent, BaseAgent)
    assert agent.llm is llm
    assert agent.db is db

@pytest.mark.asyncio
async def test_list_agents_includes_base():
    assert "base" in registry.list_agents()
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_registry.py -v` → `5 passed`

### Step 6: Final lint check

操作：
- a) Run `ruff check src/agents/` — 0 errors
- b) Run `ruff check tests/unit/test_base_agent.py tests/unit/test_agent_registry.py` — 0 errors
- c) Run `ruff format --check src/agents/ tests/unit/test_base_agent.py tests/unit/test_agent_registry.py` — all pass

**完成判定**：`ruff check src/agents/ tests/unit/test_base_agent.py tests/unit/test_agent_registry.py` → exit 0

---

## 6. 验收

- [ ] `ls src/agents/base.py src/agents/registry.py` → both files exist
- [ ] `ruff check src/agents/` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_base_agent.py -v` → `4 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_registry.py -v` → `5 passed`
- [ ] `PYTHONPATH=src python -c "from src.agents.registry import registry; assert 'base' in registry.list_agents()"` → exit 0
- [ ] `PYTHONPATH=src python -c "from src.agents.base import BaseAgent; from src.agents.registry import registry; a = registry.get('base', llm={}, db=None); print(a)"` → prints instance repr without error

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `@register` decorator used on a non-`BaseAgent` subclass silently stores wrong type | 低 | 低 | Unit test `test_register_decorator` validates type; no runtime guard needed at this stage |
| Circular import if `base.py` imports `registry` in the future | 低 | 中 | Keep imports unidirectional: `base.py` does not import `from src.agents.registry`; add `TYPE_CHECKING` guard if needed later |
| `AgentRegistry.get()` signature changes when real dependency-injection strategy is chosen (e.g. DI container) | 中 | 中 | `get()` accepts `(name, llm, db)` now; a container swap only changes the implementation, not the interface契约不变，仅实现在 `get()` 内部替换 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/agents/ tests/unit/test_base_agent.py tests/unit/test_agent_registry.py
git commit -m "feat(agents): add BaseAgent abstract class and AgentRegistry singleton

Closes #625"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(agents): BaseAgent + AgentRegistry (issue #625)" --body "## Summary
- Add src/agents/base.py: abstract BaseAgent class with llm/db injection and typed run()
- Add src/agents/registry.py: singleton AgentRegistry with @register decorator, get(), list_agents()
- Register BaseAgent under name 'base'
- Add unit tests in tests/unit/test_base_agent.py and tests/unit/test_agent_registry.py

## Test plan
- [ ] ruff check src/agents/ → 0 errors
- [ ] pytest tests/unit/test_base_agent.py -v → 4 passed
- [ ] pytest tests/unit/test_agent_registry.py -v → 5 passed

🤖 Generated with Claude Code"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD — 没有现有 agents 代码供参考；参考 Python-abc 和常见 registry-pattern 实现
- 父 issue /关联：#41

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
