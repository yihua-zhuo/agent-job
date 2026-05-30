# Implementation Plan — Issue #625

## Goal
Introduce the agent abstraction layer for the multi-agent CRM system by creating `src/agents/base.py` with an abstract `BaseAgent` class (injecting LLM and DB dependencies, defining `run(task: str) -> dict[str, Any]`) and `src/agents/registry.py` with a singleton `AgentRegistry` supporting decorator-based registration, `get()`, and `list_agents()`. Register `BaseAgent` itself as the first entry and add unit tests covering both modules.

## Affected Files
- `src/agents/__init__.py` — **new** — exports `BaseAgent`, `AgentRegistry`, `register`
- `src/agents/base.py` — **new** — abstract `BaseAgent` class
- `src/agents/registry.py` — **new** — singleton `AgentRegistry` with `@register` decorator
- `tests/unit/test_base_agent.py` — **new** — unit tests for `BaseAgent` abstract interface
- `tests/unit/test_agent_registry.py` — **new** — unit tests for `AgentRegistry` singleton

> **Note:** Test file paths and naming are verified by acceptance criterion 4, which runs the specific test files by name — moving or renaming them will cause the acceptance test to fail.

## Implementation Steps

1. **Create `src/agents/` as a Python package.** Add `src/agents/__init__.py` exporting `BaseAgent`, `AgentRegistry`, and `register`. Ruff linting for this new package will be active automatically since `ruff check src/` covers the whole `src/` tree.

2. **Create `src/agents/base.py`.** Define an abstract class extending `ABC` with an `abstractmethod run(self, task: str) -> dict[str, Any]`. The constructor accepts two injected dependencies:
   - `llm: AIChatGateway` — from `src/internal/ai_gateway.py`
   - `session: AsyncSession` — from `sqlalchemy.ext.asyncio` (typed but not defaulting to `None`)
   
   Import both dependencies at the top of the file. The `run` method body raises `NotImplementedError`. No business logic — pure interface.

3. **Create `src/agents/registry.py`.** Implement the module-level singleton pattern:
   - `_registry: AgentRegistry | None = None` module-level sentinel
   - `AgentRegistry.__new__` returns the cached instance, initialising `_agents: dict[str, type[BaseAgent]]` on first call
   - `register(name: str)` decorator — returns a callable that adds the decorated class to the registry and returns it unchanged
   - `get(name: str) -> type[BaseAgent]` — returns the class, raises `LookupError` if not found
   - `list_agents() -> list[str]` — returns sorted list of registered names

4. **Register `BaseAgent` in the registry** by adding `@register("base")` (or a semantically named key such as `"base"`) above the class definition in `base.py`. This satisfies the requirement that "BaseAgent is registered with the registry" while keeping the code self-contained in `src/agents/`.

## Test Plan

- Unit tests in `tests/unit/`:
  - `tests/unit/test_base_agent.py` — verifies `BaseAgent` is abstract (cannot be instantiated directly), `BaseAgent.run` (or a subclass that does not override `run`) raises `NotImplementedError` when called, and the constructor accepts both `llm` and `session` kwargs. Uses a minimal concrete subclass to exercise the interface. Both `llm` and `session` are mocked (no real DB connections or SQL execution).
  - `tests/unit/test_agent_registry.py` — tests singleton identity (`AgentRegistry() is AgentRegistry()`), `@register` decorator adds entries, `get` returns the correct class, `get` raises `LookupError` for unknown names, `list_agents` returns sorted names including the pre-registered entry, and that registering the same name twice raises `ValueError`. The file defines its own `mock_db_session` fixture; no real SQL is executed.

- Integration tests in `tests/integration/`: **none** — this scope is pure Python with no DB or API surface; integration tests belong to future subtasks.

## Acceptance Criteria
- `src/agents/base.py` defines `class BaseAgent(ABC)` with `@abstractmethod def run(self, task: str) -> dict[str, Any]` and a constructor accepting typed `llm` and `session` parameters
- `src/agents/registry.py` exposes `AgentRegistry`, `BaseAgent`, `register`, `get`, and `list_agents`; calling `AgentRegistry()` twice returns the same object instance
- `@register("base")` above `BaseAgent` causes `"base"` to appear in `list_agents()` output
- `pytest tests/unit/test_base_agent.py tests/unit/test_agent_registry.py -v` passes with zero errors
- `ruff check src/agents` reports no lint errors
