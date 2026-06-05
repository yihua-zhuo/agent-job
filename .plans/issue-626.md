Now I have all the information I need. The dev-plan assumes a greenfield module, but `BaseAgent`, `AgentRegistry`, and `AIChatGateway` already exist with different API contracts. I'll write a plan that correctly accounts for the real codebase.

# Implementation Plan — Issue #626

## Goal

Create `src/agents/coordinator.py` with a `CoordinatorAgent` class that extends the existing `BaseAgent`, decomposes a natural-language task into ordered `SubTask` objects via keyword-based parsing, dispatches each subtask to a registered agent looked up through the existing singleton `AgentRegistry`, and tracks per-subtask completion/failure. The plan also accounts for the fact that `BaseAgent` already exists (`src/agents/base.py`) with a different constructor signature (`__init__(self, llm, session)`) and abstract method (`run(self, task: str) -> dict`) than the dev-plan's assumed blank slate — so the dev-plan §5 Step 1 and §3.1 `src/agents/__init__.py` are no-ops and only the `coordinator.py` plus its test file are new code.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0626-add-coordinatoragent-with-task-decomposition.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0626-add-coordinatoragent-with-task-decomposition.md`

## Affected Files

- `src/agents/coordinator.py` — new file; defines `SubTask`, `TaskDecomposition`, `WorkflowResult` Pydantic models and `CoordinatorAgent(BaseAgent)` with `decompose()` and `run()` methods; uses `AgentRegistry` to dispatch subtasks to registered agent classes
- `tests/unit/test_coordinator_agent.py` — new file; unit tests with mocked sub-agent calls using `AsyncMock` for `run()`

The dev-plan §3.1 lists `src/agents/__init__.py` as a "要建" file, but it already exists (`src/agents/__init__.py` lines 1-6) and already re-exports `BaseAgent` and `AgentRegistry`. No edit is needed there. Likewise `src/agents/base.py` and `src/agents/registry.py` already exist with the correct API — only the dev-plan's Step 1 code block is a no-op replacement.

## Implementation Steps

1. **Verify existing `BaseAgent` and `AgentRegistry` contracts** — confirm that `BaseAgent.__init__(llm, session)` (from `src/agents/base.py` line 66) and `AgentRegistry.get(name) -> type[BaseAgent]` / `.list_agents() -> list[str]` (from `src/agents/registry.py` lines 52-62) match what `CoordinatorAgent` needs. The coordinator must accept `llm` and `session` in its constructor (to satisfy `BaseAgent.__init__`) but may bypass `AIChatGateway` for the rule-based parser in this issue's scope (consistent with the dev-plan §1.3 "no LLM integration" exclusion). `AgentRegistry.get()` raises `LookupError` (not `KeyError`) — coordinator's `run()` must catch that specific exception class.
2. **Create `src/agents/coordinator.py`** with Pydantic models `SubTask`, `TaskDecomposition`, `WorkflowResult` (matching dev-plan §5 Step 2 fields exactly) and `CoordinatorAgent(BaseAgent)`. The class: (a) inherits from `BaseAgent` and calls `super().__init__(llm, session)`; (b) holds a reference to `AgentRegistry` (either injected as a second constructor arg or fetched lazily as `AgentRegistry()` — pick constructor injection for testability, per dev-plan §4.1); (c) implements `name` property returning `"coordinator"`; (d) `def decompose(self, task_description: str) -> TaskDecomposition` using keyword groups: `("test",) → "test_agent"`, `("review", "code") → "code_review_agent"`, `("qc", "quality") → "qc_agent"`, fallback `("implement",) → "implement_agent"`; (e) `def _dispatch(self, decomposition: TaskDecomposition) -> WorkflowResult` that iterates `decomposition.subtasks` in order, calls `registry.get(agent_name)(llm, session).run(subtask.description)` for each, catches `LookupError` (unknown agent) and `(RuntimeError, ValueError, TypeError, AttributeError)` (agent crash), appends to `completed` or `failed` accordingly, and returns a `WorkflowResult`; (f) `def run(self, task: str) -> dict[str, Any]` — the single public override of `BaseAgent.run` — that calls `self.decompose(task)` then `self._dispatch(decomposition)` and returns `{"success": result.success, "data": result.model_dump()}`. The dispatch loop lives in a separate `_dispatch` method (not a second `run`) to keep one clear `run(task: str) -> dict` contract.
3. **Register `CoordinatorAgent` with the decorator** — add `@register("coordinator")` above the class definition in `src/agents/coordinator.py` (per the existing `register` decorator in `src/agents/base.py` line 17), so it appears in `AgentRegistry.list_agents()`. Place the import of `register` and `BaseAgent` from `agents.base` and `AgentRegistry` from `agents.registry` at the top.
4. **Create `tests/unit/test_coordinator_agent.py`** — pytest-asyncio tests covering: (1) `test_decompose_routes_test_keyword` — `"write tests for login"` → single subtask with `agent_name="test_agent"`; (2) `test_decompose_routes_code_review_keyword` — `"review the auth module"` → `"code_review_agent"`; (3) `test_decompose_falls_back_to_implement_agent` — `"do something vague"` → `"implement_agent"`; (4) `test_decompose_emits_multiple_subtasks` — `"review and qc the API"` → two subtasks in order; (5) `test_run_dispatches_to_registered_agents` — use `AgentRegistry` singleton with two mock agent classes whose `run` is `AsyncMock(return_value={"ok": True})`, call `coordinator.run(decomposition)`, assert both in `completed`; (6) `test_run_catches_unknown_agent` — decomposition references `"ghost_agent"` not in registry, assert it's in `failed` with error message naming the agent; (7) `test_run_catches_agent_exception` — register an agent class whose `run` raises `RuntimeError("boom")`, assert subtask lands in `failed` with `error == "boom"`; (8) `test_run_top_level_dispatches_end_to_end` — `await coordinator.run("review and test the login module")` returns a dict with `completed` and `failed` lists. The singleton must be reset in test setup via `_reset_registry()` (as done in `tests/unit/test_agent_registry.py` lines 10-15) to avoid leakage from other tests.
5. **Lint and format pass** — run `ruff check src/agents/coordinator.py tests/unit/test_coordinator_agent.py` and `ruff format --check src/agents/coordinator.py tests/unit/test_coordinator_agent.py`; resolve any import-ordering or line-length findings.

## Test Plan

- Unit tests in `tests/unit/`: add `tests/unit/test_coordinator_agent.py` with the 8 test cases listed in Step 4. Each test resets the `AgentRegistry` singleton (per the pattern in `tests/unit/test_agent_registry.py` lines 10-15) and registers lightweight `BaseAgent` subclasses with `AsyncMock` `run` methods. No integration tests required (the dev-plan §1.3 explicitly excludes DB persistence, and `CoordinatorAgent` is an in-memory orchestration component).
- Dev-plan verification: §6 lists five machine-checkable commands — `ruff check src/agents/`, `ruff check tests/unit/test_coordinator_agent.py`, `python -c "from agents.coordinator import CoordinatorAgent; print('import OK')"`, `pytest tests/unit/test_coordinator_agent.py -v` (≥ 6 passed per dev-plan §1.4, but 8 with the expanded test set), and `ruff format --check src/agents/`. All five are runnable once Steps 1-4 complete; no board-specific verify script exists in the repo.

## Acceptance Criteria

- `PYTHONPATH=src ruff check src/agents/` → 0 errors
- `PYTHONPATH=src ruff check tests/unit/test_coordinator_agent.py` → 0 errors
- `PYTHONPATH=src python -c "from agents.coordinator import CoordinatorAgent, SubTask, TaskDecomposition, WorkflowResult"` exits silently (import success)
- `PYTHONPATH=src pytest tests/unit/test_coordinator_agent.py -v` → ≥ 6 passed (8 with expanded cases)
- `CoordinatorAgent` appears in `AgentRegistry().list_agents()` as `"coordinator"` (via the `@register` decorator)
- `decompose()` produces a `TaskDecomposition` whose `subtasks` list contains one `SubTask` per matched keyword group, each with a unique `id` and the correct `agent_name`
- `run()` catches both `LookupError` (unknown agent) and arbitrary `Exception` (agent crash), routing the subtask to `WorkflowResult.failed` with the error message in `subtask.result["error"]`
- Successful dispatches land in `WorkflowResult.completed` with `subtask.status == "completed"` and `subtask.result` populated from the agent's return value

## Risks / Open Questions

- **Dev-plan API mismatch**: The dev-plan's §5 Step 1 and Step 3 define `BaseAgent` with `async execute(self, task: dict) -> dict` and `AgentRegistry.get()` returning a `BaseAgent` instance raising `KeyError`. The actual code (`src/agents/base.py` line 71, `src/agents/registry.py` line 52-56) uses `run(self, task: str) -> dict` and `LookupError`. The implementation must follow the actual code, not the dev-plan's assumed API. The dev-plan board should be updated post-implementation to reflect the real signatures (or the dev-plan generator needs to read existing code before generating boards for issues in already-implemented categories).
- **Singleton leakage**: `AgentRegistry` is a process-wide singleton (`registry.py` line 30-41). Tests that register mock agents must call `_reset_registry()` in setup or teardown, otherwise test order coupling can cause `LookupError` or duplicate-name `ValueError` failures. The test file should use a pytest fixture (`autouse=True`) that resets the registry before each test.
- **Synchronous vs. async `run`**: `BaseAgent.run` is declared `def` (not `async def`) in `src/agents/base.py` line 71, yet the existing test (`test_base_agent.py` line 47-48) calls it without `await`. If `CoordinatorAgent.run` is implemented as `async def` to allow async dispatch, it would violate the `BaseAgent` ABC contract. Resolution: implement `run` as synchronous, using `asyncio.run` internally or by making the dispatch synchronous (calling each agent's `run` directly, not via `await`). This keeps the ABC contract and matches the pattern in `test_base_agent.py`.
