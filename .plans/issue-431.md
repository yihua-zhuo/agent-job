# Implementation Plan — Issue #431

## Goal

Refactor `CustomerService.__init__` to accept only a `CustomerRepository` (no `session`, no `None` default), and migrate the three remaining methods that call `self.session.execute(...)` directly (`get_unassigned_leads`, `get_leads_by_owner`, `bulk_recycle`) to delegate through the repository instead. Tests and router call sites are updated to match.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0431-wire-customerrepository-into-customerservice.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0431-wire-customerrepository-into-customerservice.md`

## Affected Files

- `src/services/customer_service.py` — rewrite `__init__` to accept `repository: CustomerRepository` only; migrate 3 methods to delegate via `self.repository`
- `src/db/repositories/customer.py` — add 3 new async methods: `get_unassigned_leads`, `get_leads_by_owner`, `bulk_recycle`
- `src/api/routers/customers.py` — update all 17 `CustomerService(session, CustomerRepository(session))` call sites to construct `CustomerRepository(session)` once and pass it
- `tests/unit/test_customer_service.py` — update `mock_db_session` fixture (remove unused session mock); ensure all tests pass with repository-only init

## Implementation Steps

1. **Add three methods to `CustomerRepository`** (`src/db/repositories/customer.py`)

   Add `get_unassigned_leads`, `get_leads_by_owner`, and `bulk_recycle` — mirroring the logic currently in `customer_service.py` but using `self.session` directly (which the repository already holds):

   ```python
   async def get_unassigned_leads(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[CustomerModel], int]:
       """Return leads with owner_id=0 and status=lead, ordered by created_at."""
       conditions = [CustomerModel.tenant_id == tenant_id, CustomerModel.owner_id == 0, CustomerModel.status == "lead"]
       count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
       total = count_result.scalar() or 0
       offset = (page - 1) * page_size
       result = await self.session.execute(
           select(CustomerModel).where(and_(*conditions)).order_by(CustomerModel.created_at.asc()).offset(offset).limit(page_size)
       )
       return list(result.scalars().all()), total

   async def get_leads_by_owner(self, tenant_id: int, owner_id: int, page: int = 1, page_size: int = 20) -> tuple[list[CustomerModel], int]:
       """Return leads for a specific owner."""
       conditions = [CustomerModel.tenant_id == tenant_id, CustomerModel.owner_id == owner_id, CustomerModel.status == "lead"]
       count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
       total = count_result.scalar() or 0
       offset = (page - 1) * page_size
       result = await self.session.execute(
           select(CustomerModel).where(and_(*conditions)).order_by(CustomerModel.created_at.asc()).offset(offset).limit(page_size)
       )
       return list(result.scalars().all()), total

   async def bulk_recycle(self, customer_ids: list[int], tenant_id: int) -> list[int]:
       """Set owner_id=0, increment recycle_count, append history for matching leads. Returns recycled IDs."""
       if not customer_ids:
           return []
       now = datetime.now(UTC)
       result = await self.session.execute(
           select(CustomerModel).where(and_(CustomerModel.tenant_id == tenant_id, CustomerModel.id.in_(customer_ids), CustomerModel.status == "lead", CustomerModel.owner_id != 0))
       )
       leads = result.scalars().all()
       if not leads:
           return []
       for lead in leads:
           history = list(lead.recycle_history or [])
           history.append({"recycled_at": now.isoformat(), "previous_owner_id": lead.owner_id, "reason": "manual_bulk_recycle"})
           await self.session.execute(
               update(CustomerModel).where(and_(CustomerModel.id == lead.id, CustomerModel.tenant_id == tenant_id)).values(owner_id=0, assigned_at=None, recycle_count=lead.recycle_count + 1, recycle_history=history, updated_at=now)
           )
       await self.session.flush()
       return [lead.id for lead in leads]
   ```

   **完成判定**: `ruff check src/db/repositories/customer.py` → 0 errors

2. **Rewrite `CustomerService.__init__` in `src/services/customer_service.py`**

   Replace:
   ```python
   def __init__(self, session: AsyncSession, customer_repo: CustomerRepository | None = None):
       self.session = session
       self.customer_repo = customer_repo if customer_repo is not None else CustomerRepository(session)
   ```
   With:
   ```python
   def __init__(self, repository: CustomerRepository) -> None:
       self.repository = repository
   ```
   - Remove `from sqlalchemy.ext.asyncio import AsyncSession` import (no longer used)
   - Rename all `self.customer_repo` references to `self.repository` throughout the file (appears in existing delegating methods)

3. **Migrate the three methods that still call `self.session.execute(...)`**

   In `src/services/customer_service.py`, replace each of these method bodies to delegate to `self.repository`:

   `get_unassigned_leads`:
   ```python
   async def get_unassigned_leads(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Any], int]:
       return await self.repository.get_unassigned_leads(tenant_id, page, page_size)
   ```
   (Remove the inline SQLAlchemy imports `from sqlalchemy import and_, func, select` and `from db.models.customer import CustomerModel` from this method)

   `get_leads_by_owner`:
   ```python
   async def get_leads_by_owner(self, owner_id: int, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Any], int]:
       return await self.repository.get_leads_by_owner(owner_id, tenant_id, page, page_size)
   ```

   `bulk_recycle`:
   ```python
   async def bulk_recycle(self, customer_ids: list[int], tenant_id: int) -> list[int]:
       return await self.repository.bulk_recycle(customer_ids, tenant_id)
   ```

   **完成判定**: `grep -c "self.session.execute" src/services/customer_service.py` → `0`

4. **Remove `self.session` from `LeadRoutingService` construction**

   In `create_customer` method, change `LeadRoutingService(self.session)` to `LeadRoutingService(self.repository.session)`. Verify `LeadRoutingService.__init__` accepts `AsyncSession`.

   **完成判定**: `ruff check src/services/customer_service.py` → 0 errors

5. **Update `src/api/routers/customers.py` call sites**

   Replace all occurrences of:
   ```python
   service = CustomerService(session)
   ```
   with a pre-constructed repository near the top of each handler function (or per-endpoint), e.g.:
   ```python
   repo = CustomerRepository(session)
   service = CustomerService(repo)
   ```
   If multiple endpoints share a session, hoist the repository instantiation within each endpoint handler. No change to router method signatures or response shapes.

   **完成判定**: `grep "CustomerService(session" src/api/routers/customers.py` → no output

6. **Update `tests/unit/test_customer_service.py`**

   - The `mock_db_session` fixture is still present but no longer needs `session.execute`, `session.add`, `session.flush`, `session.refresh` — strip it down or remove it if unused
   - The `mock_customer_repo` fixture (already present, constructed via `_make_mock_customer_repo()`) covers all 14 repository methods including the 3 new ones
   - Ensure `TestEnrichmentUpsert` tests (which still call `CustomerService(mock_db_session)` with no repo) are updated to pass `mock_customer_repo` instead, or mock `service.customer_repo` directly on the service instance
   - Add mock for `repository.session` (needed by `LeadRoutingService` in `create_customer`):
     ```python
     mock_customer_repo.session = MagicMock()  # for LeadRoutingService(self.repository.session)
     ```

   **完成判定**: `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all pass

7. **Full unit test suite regression check**

   ```bash
   PYTHONPATH=src pytest tests/unit/ -v
   ```

   **完成判定**: exit 0, all tests pass, no new failures

8. **Lint check**

   ```bash
   ruff check src/services/customer_service.py src/db/repositories/customer.py src/api/routers/customers.py
   ```

   **完成判定**: 0 errors

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_customer_service.py` — update `mock_db_session` fixture (remove if unused); verify all existing tests pass with repository-only `__init__`; ensure `TestEnrichmentUpsert` tests work with mocked `customer_repo`
- **Integration tests in `tests/integration/`**: No new integration tests needed — schema unchanged; router behavior unchanged
- **Dev-plan verification**:
  - Step 1: `ruff check src/db/repositories/customer.py` → 0 errors
  - Step 2+3: `grep -c "self.session.execute" src/services/customer_service.py` → `0`
  - Step 5: `grep "CustomerService(session" src/api/routers/customers.py` → no output
  - Step 6: `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all passed
  - Step 7: `PYTHONPATH=src pytest tests/unit/ -v` → exit 0
  - Step 8: `ruff check src/services/customer_service.py src/db/repositories/customer.py src/api/routers/customers.py` → 0 errors

## Acceptance Criteria

- `CustomerService.__init__` accepts exactly one argument: `repository: CustomerRepository` (no `AsyncSession`, no default)
- `grep "self.session" src/services/customer_service.py` returns 0 results (all `self.session` removed)
- `ruff check src/services/customer_service.py src/db/repositories/customer.py src/api/routers/customers.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all tests pass
- `PYTHONPATH=src pytest tests/unit/ -v` → no regressions (exit 0)
- All router endpoints use `CustomerService(repo)` form
