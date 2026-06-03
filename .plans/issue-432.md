Now I have a complete picture of the codebase. Let me write the implementation plan.

# Implementation Plan — Issue #432

## GoalUpdate the mock layer in `tests/unit/` to add a `make_customer_repository_handler(state)` in the domain handler module pattern (wired via `tests/unit/domain_handlers/customers.py`), and register it in the `mock_db_session` fixture in `tests/unit/test_customer_service.py`. All existing test cases pass unchanged — only the mock infrastructure changes.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0432-update-test-customer-service-py-mocks-for-customerrepository.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0432-update-test-customer-service-py-mocks-for-customerrepository.md`

## Affected Files

- `tests/unit/domain_handlers/customers.py` — add `make_customer_repository_handler(state)` aligned to `CustomerRepository` method signatures; update `__all__` and `get_handlers()`
- `tests/unit/test_customer_service.py` — update `mock_db_session` fixture to use `make_mock_session` with the domain handler pattern including the new repository handler

## Implementation Steps

### Step 1: Add `make_customer_repository_handler` to `tests/unit/domain_handlers/customers.py`

In `tests/unit/domain_handlers/customers.py`, add a new handler factory `make_customer_repository_handler(state)` after the existing `make_customer_handler`, following the same function signature and style. The handler receives `(sql_text, params)` and returns `MockResult` for queries it handles (SELECT / INSERT / UPDATE / DELETE), or `None` to fall through. It must mock the `CustomerRepository`-calling SQL patterns:

- `INSERT INTO customer_enrichment` → return `MockResult([MockRow({...})])`
- `SELECT FROM customers WHERE id = :id AND tenant_id = :tenant_id` → return stored state record from `state.customers[id]` or factory fixture
- `SELECT FROM customers WHERE tenant_id = :tenant_id …` (list) → return all records for tenant from `state.customers`
- `SELECT status, count(id) FROM customers WHERE tenant_id = :tenant_id GROUP BY status` → return status-count tuples matching `state.customers`
- `SELECT … FROM customers WHERE tenant_id = :tenant_id AND (name ILIKE OR email ILIKE)` → search filter from state
- `UPDATE customer_enrichment …` / `INSERT INTO customer_enrichment … ON CONFLICT` → upsert patternAppend the handler to `get_handlers()` and add `make_customer_repository_handler` to `__all__`.

**Completion check**: `ruff check tests/unit/domain_handlers/customers.py` → 0 errors.

### Step 2: Update `mock_db_session` fixture to use `make_mock_session`

In `tests/unit/test_customer_service.py`, replace the existing `mock_db_session` fixture (which creates a plain `MagicMock` session with hard-coded return values) with a `make_mock_session` call that includes `make_customer_repository` domain handlers:

```python
@pytest.fixture
def mock_db_session():
    from tests.unit.conftest import MockState, make_mock_session
    from tests.unit.domain_handlers.customers import make_customer_handler, make_customer_repository_handler
    from tests.unit.domain_handlers.counts import make_count_handler
    state = MockState()
    return make_mock_session([
        make_customer_handler(state),
        make_customer_repository_handler(state),
        make_count_handler(state),
    ])
```

**Completion check**: `ruff check tests/unit/test_customer_service.py` → 0 errors.

### Step 3: Run unit tests

```bash
PYTHONPATH=src pytest tests/unit/test_customer_service.py -v
```

All existing test cases pass (each test also uses its own `mock_customer_repo` — a `MagicMock` stub for the `CustomerRepository` passed directly to `CustomerService(…)`, which is orthogonal to the SQL mock).

**Completion check**: output contains only `PASSED` results; 0 `FAILED`.

## Test Plan

- Unit tests in `tests/unit/`: `tests/unit/test_customer_service.py` — all existing cases pass; no assertion or call-pattern changes to the actual test methods (the only change is replacing the `mock_db_session` fixture body)
- Integration tests in `tests/integration/`: none (this issue touches only unit-test mock infrastructure)
- Dev-plan verification per §6:
  - `ruff check tests/unit/test_customer_service.py tests/unit/conftest.py tests/unit/domain_handlers/customers.py` →0 errors
  - `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all passed  - `PYTHONPATH=src pytest tests/unit/ -v --ignore=tests/unit/domain_handlers/` → no new failures introduced

## Acceptance Criteria

- `ruff check` on all touched files exits 0
- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all existing test cases pass with unchanged assertions
- `make_customer_repository_handler` is callable via `from tests.unit.domain_handlers.customers import make_customer_repository_handler`
- `mock_db_session` fixture in `test_customer_service.py` uses `make_mock_session` with domain handlers (not a bare `MagicMock`)

## Risks / Open Questions

- The existing `mock_db_session` fixture is currently used in 0 test methods (tests call `CustomerService(mock_customer_repo)` directly, not via the SQL-mocked session path). The refactor is safe — but the new fixture structure must also support tests that need seeded SQL state if any are added later. Passing `state` explicitly in the fixture ensures per-test isolation.
