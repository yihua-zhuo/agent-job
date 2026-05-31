# Implementation Plan — Issue #430

## Goal
Extract the data-access layer from `CustomerService` into a dedicated `CustomerRepository` class in `src/db/repositories/customer.py` that subclasses `BaseRepository`. The repository handles all `CustomerModel`-specific SQL queries (create, list, get_by_id, update, delete, count_by_status, search, add_tag, remove_tag, bulk_import), using `session.flush()` instead of `session.commit()` for consistency with the current service behavior. The service retains business logic (lead auto-assignment trigger, status validation). This is a pure refactor — no behavior changes.

## Affected Files
- `src/db/repositories/customer.py` — **new file** — `CustomerRepository` class
- `src/db/repositories/__init__.py` — re-export `CustomerRepository`
- `src/services/customer_service.py` — inject `CustomerRepository` (or accept session-only constructor that the repo will be built around); delegate all SQL to `CustomerRepository`, keep business logic (lead auto-assign, VALID_STATUSES check)
- `tests/unit/test_customer_service.py` — update any tests that directly assert SQL behavior moved to the repository; mock `CustomerRepository` instead of raw SQL where appropriate
- `tests/unit/test_customers_router.py` — update mocks if `CustomerService` signature changes
- `tests/unit/test_customer_repository.py` — **new file** — unit tests for `CustomerRepository`

## Implementation Steps

1. **Create `src/db/repositories/customer.py`**
   - Define `class CustomerRepository(BaseRepository)`
   - Constructor: `def __init__(self, session: AsyncSession)` — pass to super
   - Implement all CustomerModel-specific query methods by moving their SQL logic from `CustomerService`:
     - `create(data: dict, tenant_id: int) -> CustomerModel` — build `CustomerModel` from dict, `session.add()`, `session.flush()`, return the object (no auto-assignment trigger — that's service-layer)
     - `list_customers(tenant_id: int, page, page_size, status, owner_id) -> tuple[list[CustomerModel], int]`
     - `get_customer(customer_id: int, tenant_id: int) -> CustomerModel` — raises `NotFoundException("客户")` on missing
     - `update_customer(customer_id: int, data: dict, tenant_id: int) -> CustomerModel | None` — raises `ValidationException` for invalid status, calls `get_customer`, mutates attrs, `session.flush()`, `session.refresh()`, return updated object; returns `None` if no allowed fields changed
     - `delete_customer(customer_id: int, tenant_id: int) -> dict` — raises `NotFoundException("客户")` if rowcount==0, returns `{"id": customer_id}`; note: do NOT call `session.commit()` — use `session.flush()` to be consistent with service behavior, or note that callers (service) own the flush cycle
     - `count_by_status(tenant_id: int) -> dict[CustomerStatus, int]`
     - `search_customers(keyword: str, tenant_id: int) -> list[CustomerModel]` — escape wildcards, `ilike`, limit 100, order by `created_at.desc()`
     - `add_tag(customer_id: int, tag: str, tenant_id: int) -> CustomerModel`
     - `remove_tag(customer_id: int, tag: str, tenant_id: int) -> CustomerModel`
     - `bulk_import(customers: list[dict], tenant_id: int) -> int` — build `CustomerModel` list, `session.add_all()`, `session.flush()`, return count
   - For every mutation method, use `await self.session.flush()` (not `commit()`) so callers own the flush cycle
   - Raise `NotFoundException("客户")` and `ValidationException` using the same messages as `CustomerService`

2. **Update `src/db/repositories/__init__.py`**
   - Add `from db.repositories.customer import CustomerRepository` and add it to `__all__`

3. **Refactor `src/services/customer_service.py`**
   - Change `CustomerService.__init__` to accept `customer_repo: CustomerRepository` (not `session: AsyncSession`)
   - Keep `self.session = session` internally if business-logic methods (e.g. `reassign_lead`, `bulk_recycle`, `create_customer` auto-assignment trigger) need raw session access; alternatively store both `customer_repo` and `session`
   - Replace each method's SQL with a call to the corresponding repository method
   - Keep business-only logic in the service: the auto-assignment trigger in `create_customer`, `VALID_STATUSES` check, `reassign_lead` history management, `bulk_recycle` lead-collection logic
   - For `create_customer`: repository creates the object and flushes; service then runs the auto-assignment trigger using `self.session`

4. **Create `tests/unit/test_customer_repository.py`**
   - Use `MockState`, `MockRow`, `MockResult`, `make_mock_session` from `conftest.py`
   - Define a `mock_db_session` fixture with handlers that simulate the `CustomerRepository` SQL patterns
   - Test each method: happy path, not-found (raises `NotFoundException`), invalid status (raises `ValidationException`)
   - Test `search_customers` with empty keyword returns `[]`
   - Test `bulk_import` with empty list returns `0`
   - Test `count_by_status` returns correct `dict[CustomerStatus, int]`
   - Do NOT test `add_tag` adding a duplicate (idempotent), and `remove_tag` removing a non-existent tag

5. **Update `tests/unit/test_customer_service.py`**
   - Replace SQL-level mock setups with mocks of `CustomerRepository` methods where appropriate
   - If `CustomerService` now accepts a `CustomerRepository` in its constructor, update service fixtures accordingly

6. **Run full test suite**
   - `ruff check src/` — must pass
   - `ruff format --check src/` — must pass
   - `mypy src/` — must pass
   - `pytest tests/unit/ -v` — all unit tests pass
   - `pytest tests/integration/ -v` (with a live DB) — all integration tests pass

## Test Plan
- **Unit tests in `tests/unit/`**: `tests/unit/test_customer_repository.py` — new file covering all 10 repository methods; `tests/unit/test_customer_service.py` — updated to mock `CustomerRepository` instead of raw SQL where applicable
- **Integration tests in `tests/integration/`**: no new integration test files needed; existing `tests/integration/test_customer_service_integration.py` (if present) covers end-to-end behavior with the real DB and will continue to pass since `CustomerRepository` delegates to the same SQLAlchemy models

## Acceptance Criteria
- `CustomerRepository` is importable via `from db.repositories import CustomerRepository`
- All 10 methods are present and have the correct signatures matching the SQL behavior currently in `CustomerService`
- Mutation methods use `session.flush()`, not `session.commit()`
- `NotFoundException("客户")` is raised on missing lookups; `ValidationException` on invalid status
- `ruff check src/` and `ruff format --check src/` pass with no errors
- `mypy src/` passes with no errors
- `pytest tests/unit/ -v` passes with no failures
- `CustomerService` still triggers auto-assignment for new leads with no owner after `create_customer`

## Risks / Open Questions
- `BaseRepository.delete_by_id` calls `session.commit()` internally, but `CustomerService.delete_customer` does not — since `CustomerRepository` subclasses `BaseRepository`, the override of `delete_customer` must NOT call the parent's `delete_by_id` (which commits) and instead use raw SQL with `flush()` to match existing service behavior.
- `create_customer` in the service has a side effect (auto-assignment trigger) that must be preserved — the repository handles the flush, the service runs the trigger afterward.
- `reassign_lead`, `bulk_recycle`, `get_unassigned_leads`, `get_leads_by_owner`, `change_status`, `assign_owner` are not listed in the issue scope but live in `CustomerService` — they should stay in the service; only the explicitly listed methods move to the repository.
