# Implementation Plan — Issue #623

## Goal

Add `agent_tasks` and `agent_tasks_next_id` fields to `MockState.__init__` in `tests/unit/conftest.py`, completing the `MockState` interface expected by the domain handler in `tests/unit/domain_handlers/agent_tasks.py`. The test files and domain handler already exist and are comprehensive.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0623-add-unit-tests-for-agenttaskservice-and-router.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0623-add-unit-tests-for-agenttaskservice-and-router.md`

## Affected Files

- `tests/unit/conftest.py` — add two fields to `MockState.__init__`

## Implementation Steps

1. **Add `agent_tasks` and `agent_tasks_next_id` to `MockState`** in `tests/unit/conftest.py`:
   - Add `self.agent_tasks: dict = {}` and `self.agent_tasks_next_id: int = 1` to the `__init__` body.
   - The domain handler in `tests/unit/domain_handlers/agent_tasks.py` already uses `hasattr` guards, so this change is additive only.

## Test Plan

- Unit tests in `tests/unit/`:
  - `tests/unit/test_agent_task_service.py` — already exists (209 lines); covers: `atask_` prefix on create, `NotFoundException` on missing id, `list_tasks` with status filter and tenant isolation, pagination, date-range filtering.
  - `tests/unit/test_agent_tasks.py` — already exists (223 lines); covers: POST 201 envelope, GET list envelope with `items`/`total`/`has_next`/`page`/`page_size`, GET 404 from `NotFoundException`, status query param, pagination bounds.
- `tests/unit/domain_handlers/agent_tasks.py` — already exists; provides `make_agent_task_handler(state)` and `get_handlers(state)`.
- Dev-plan verification (per dev-plan §6):
  - `ruff check tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py tests/unit/domain_handlers/agent_tasks.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py tests/unit/test_agent_tasks.py -v` → ≥ 10 passed total (service ≥ 4, router ≥ 6)
  - `PYTHONPATH=src python -c "from tests.unit.domain_handlers.agent_tasks import get_handlers, make_agent_task_handler"` → exit 0

## Acceptance Criteria

- `MockState` in `tests/unit/conftest.py` has `agent_tasks: dict` and `agent_tasks_next_id: int` fields
- `ruff check tests/unit/test_agent_task_service.py tests/unit/test_agent_tasks.py tests/unit/domain_handlers/agent_tasks.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py tests/unit/test_agent_tasks.py -v` → all passed (≥ 10)
- `PYTHONPATH=src python -c "from tests.unit.domain_handlers.agent_tasks import get_handlers, make_agent_task_handler"` → exit 0
