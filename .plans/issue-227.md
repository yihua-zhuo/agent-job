# Implementation Plan — Issue #227

## Goal
Add a `CustomerCreateDTO` dataclass to `src/models/customer.py` (after `CustomerStatus`, before `Customer`) and refactor `CustomerService.create_customer` to use direct DTO field access instead of the current dict-based pattern.

## Affected Files
- `src/models/customer.py` — Add `CustomerCreateDTO` dataclass with `name`, `email`, `phone`, `company`, `status`, `owner_id`, `tags` fields; add `from_dict` classmethod
- `src/services/customer_service.py` — Update import to `from models.customer import CustomerCreateDTO, CustomerStatus`; replace `d.get("name")` etc. with `dto.name`, `dto.email` etc. (direct field access on the already-coerced `dto`)
- `tests/unit/test_customer_service.py` — Add `test_create_customer_with_dto` under `TestCreateCustomerService`

## Implementation Steps
1. **Add `CustomerCreateDTO` to `src/models/customer.py`**: Insert a `@dataclass` after the closing `BLOCKED` line of `CustomerStatus`, before the `@dataclass class Customer` line at line 22. Fields: `name: str`, `email: str`, `phone: str | None = None`, `company: str | None = None`, `status: CustomerStatus = CustomerStatus.LEAD`, `owner_id: int = 0`, `tags: list[str] = field(default_factory=list)`. Add `from dataclasses import field` to the existing import line 3 if not already present. Add a `from_dict` classmethod that raises `ValueError` for missing/empty `name` or `email`, mirroring the `Customer.from_dict` pattern.
2. **Update the import in `src/services/customer_service.py`**: Change `from models.customer_create_dto import CustomerCreateDTO` (line 11) to `from models.customer import CustomerCreateDTO, CustomerStatus`. The `CustomerStatus` re-export from `customer_create_dto.py` is no longer needed as the primary source.
3. **Refactor `create_customer` in `src/services/customer_service.py`**: The existing `isinstance` branching at lines 34–45 already coerces the DTO to a `d` dict. After that coercion block, replace `d.get("name") or "Customer"` with `dto.name` (using the coerced `dto` variable), and replace `d.get("email")` etc. with `dto.email`, `dto.phone`, `dto.company`, `dto.status.value` (since `CustomerModel.status` is a string column), `dto.owner_id`, and `dto.tags`. Keep the fallback `"Customer"` for `name` only in the `else` (dict) branch.
4. **Add `test_create_customer_with_dto` to `tests/unit/test_customer_service.py`**: Inside `TestCreateCustomerService`, add an `@pytest.mark.asyncio async def test_create_customer_with_dto(self, mock_db_session)` that sets `mock_db_session.refresh` to a fake that sets `obj.id = 10, obj.name = "DTO Customer", obj.status = "customer"`, then calls `service.create_customer(CustomerCreateDTO(name="DTO Customer", email="dto@test.com", status=CustomerStatus.CUSTOMER), tenant_id=1)`, asserts `result.data['name'] == 'DTO Customer'` and `result.data['status'] == 'customer'`. Note: the router is responsible for `.to_dict()` serialization, so the test should call the service directly and assert on the returned `CustomerModel` fields (e.g., `result.name`, `result.status`), matching the existing test pattern in this file.

## Test Plan
- Unit tests in `tests/unit/test_customer_service.py`: Add `test_create_customer_with_dto` to the existing `TestCreateCustomerService` class. Existing tests (`test_create_customer_accepts_dict`, `test_create_customer_accepts_dto`, `test_create_customer_empty_dict_uses_defaults`) cover the dict and DTO service integration paths and the empty-dict fallback. All six `test_create_customer`-matching tests plus the full suite in the file must pass.
- Integration tests in `tests/integration/`: No changes needed — integration tests use the real ORM and the service's `isinstance(data, CustomerCreateDTO)` branching works identically with real sessions.

## Acceptance Criteria
- `python3 -c 'from src.models.customer import CustomerCreateDTO, CustomerStatus; dto = CustomerCreateDTO(name="test"); print(dto.name, dto.status)'` prints `test lead` (no error)
- `ruff check src/` passes with no new violations
- `pytest tests/unit/test_customer_service.py -v -k 'test_create_customer'` shows all matching tests passing (6+ tests)
- `pytest tests/unit/test_customer_service.py -q` shows the full suite green
