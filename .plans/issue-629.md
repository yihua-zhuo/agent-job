The real `test_agent.py` exits 0 when invoked with `--task '{}'`. Now I have everything needed.

# Implementation Plan — Issue #629

## Goal
Add an integration test file (`tests/integration/test_coordinator_agent_integration.py`) that exercises `CoordinatorAgent.run_workflow()` against a real PostgreSQL session, covering happy-path (task dispatch completes), boundary (empty task list), and error (nonexistent agent → `not_found`) scenarios.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0629-add-integration-tests-for-coordinatoragent.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0629-add-integration-tests-for-coordinatoragent.md`

## Affected Files
- `tests/integration/test_coordinator_agent_integration.py` — new file; integration tests for `CoordinatorAgent.run_workflow`

## Implementation Steps

1. **Create the test file** at `tests/integration/test_coordinator_agent_integration.py` with a `sys.path` bootstrap that adds `src/` so that `from docs.agents.coordinator.coordinator_agent import CoordinatorAgent` resolves.

2. **Write the happy-path test** (`test_run_workflow_dispatches_task_and_returns_completed`):
   - Create a pytest fixture `workspace` using `tmp_path` that constructs `workspace/agents/test/test_agent.py` by copying or writing the real test agent script (which exits 0 when invoked with `--task`).
   - Instantiate `CoordinatorAgent(workspace=workspace)`.
   - Call `run_workflow([{"task_id": "t1", "assignee": "test", "type": "feature"}])`.
   - Assert `results["dispatched"]` has length 1 and `results["dispatched"][0]["status"] == "completed"`.
   - Accept `tenant_id` and `async_session` fixtures from conftest (used transitively for session lifecycle validation, matching the dev-plan pattern).

3. **Write the boundary test** (`test_run_workflow_with_empty_task_list_returns_empty_dispatched`):
   - Call `run_workflow([])`.
   - Assert `results["dispatched"] == []`, `results["completed"] == []`, `results["failed"] == []`.

4. **Write the error test** (`test_run_workflow_with_nonexistent_agent_returns_not_found`):
   - Call `run_workflow([{"task_id": "t2", "assignee": "nonexistent_agent", "type": "feature"}])`.
   - Assert `results["dispatched"][0]["status"] == "not_found"`.

5. **Verify lint** with `ruff check tests/integration/test_coordinator_agent_integration.py` to ensure 0 errors.

## Test Plan
- Unit tests in `tests/unit/`: none — dev-plan scope is integration tests only (§1.3 excludes unit tests).
- Integration tests in `tests/integration/`: new file `test_coordinator_agent_integration.py` with 3 test cases:
  - happy-path: dispatches a real agent script and gets `status == "completed"`
  - boundary: empty task list returns empty results dict
  - error: nonexistent agent returns `status == "not_found"`
- Dev-plan verification:
  - Step 1 completion: `ruff check tests/integration/test_coordinator_agent_integration.py` → exit 0
  - Step 2 completion: `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_dispatches_task_and_returns_completed -v` → 1 passed
  - Step 3 completion: `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_with_empty_task_list_returns_empty_dispatched -v` → 1 passed
  - Step 4 completion: `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_with_nonexistent_agent_returns_not_found -v` → 1 passed
  - §6 final acceptance: `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py -v` → 3 passed

## Acceptance Criteria
- `tests/integration/test_coordinator_agent_integration.py` exists and is ≥ 50 lines.
- The file imports `CoordinatorAgent` from `docs.agents.coordinator.coordinator_agent` successfully.
- 3 test cases pass: happy-path (1 dispatched, status completed), boundary (empty list), error (not_found).
- `ruff check tests/integration/test_coordinator_agent_integration.py` → 0 errors.
- `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py -v` → 3 passed.
- No changes to `conftest.py`, `coordinator_agent.py`, or any other production file.
