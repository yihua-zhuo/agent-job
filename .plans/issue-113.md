Now I have a thorough understanding of the codebase. Here is the implementation plan:

---

# Implementation Plan — Issue #113

## Goal
Add a new `GET /api/v1/sla/summary` endpoint that returns server-side aggregated SLA counts (`breached`, `at_risk`, `on_track`, `total_tickets`) from the full tenant-scoped ticket dataset, replacing the frontend's client-side computation from a single paginated page.

## Affected Files
- `src/services/sla_service.py` — add `get_sla_summary(tenant_id)` method computing the three counts
- `src/api/routers/tickets.py` — add `GET /sla/summary` endpoint and a response Pydantic schema
- `tests/unit/test_sla_service.py` — new file; unit tests for `get_sla_summary` with mocked DB
- `tests/integration/test_sla_integration.py` — new file; integration tests using real DB fixtures

## Implementation Steps

1. **Add `get_sla_summary` to `SLAService`** (`src/services/sla_service.py`):
   - Add `async def get_sla_summary(self, tenant_id: int) -> dict[str, int]`
   - Issue three `SELECT COUNT(...) FROM tickets WHERE tenant_id = :tenant_id AND ...` queries (one per bucket, no pagination) using `func.count(TicketModel.id)` and SQLAlchemy `and_()` conditions
   - `breached`: `resolved_at IS NULL AND response_deadline IS NOT NULL AND response_deadline < now`
   - `at_risk`: `resolved_at IS NULL AND response_deadline IS NOT NULL AND response_deadline > now AND response_deadline <= now + timedelta(hours=4)`
   - `on_track`: all other tickets (i.e. `resolved_at IS NOT NULL OR response_deadline IS NULL OR response_deadline > now + 4 hours`); alternatively compute as `total - breached - at_risk` to avoid double-querying
   - `total_tickets`: simple `COUNT(*)` filtered by `tenant_id` only
   - Return `{"breached": N, "at_risk": N, "on_track": N, "total_tickets": N}`
   - Use `datetime.now(UTC)` and `timedelta(hours=4)` for time comparisons (same pattern as existing `get_sla_breaches`)

2. **Add response schema and endpoint to `tickets.py`** (`src/api/routers/tickets.py`):
   - Add a `SLAStatCard(BaseModel)` schema with `breached: int`, `at_risk: int`, `on_track: int`, `total_tickets: int` fields
   - Add `GET /sla/summary` to `tickets_router` (in the existing `# SLA endpoints` section alongside `check_sla_status` and `get_sla_breach_tickets`):
     ```
     @tickets_router.get("/sla/summary")
     async def get_sla_summary(
         ctx: AuthContext = Depends(require_auth),
         session: AsyncSession = Depends(get_db),
     ):
         """Return aggregated SLA counts across the full ticket dataset for the current tenant."""
         sla_svc = SLAService(session)
         counts = await sla_svc.get_sla_summary(tenant_id=ctx.tenant_id or 0)
         return {"success": True, "data": counts}
     ```
   - The endpoint requires auth (same as other SLA endpoints) and uses the standard dependency injection pattern

3. **Write unit tests** (`tests/unit/test_sla_service.py` — new file):
   - Create `MockSlaTicket` class mimicking `TicketModel` with `id`, `tenant_id`, `status`, `resolved_at`, `response_deadline` fields and a `check_sla_breach()` method
   - Define a `mock_sla_db_session(state, tickets)` fixture that returns pre-seeded tickets matching given conditions (breached, at_risk, on_track) on the appropriate SQL `select count... from tickets` queries
   - Test cases: all categories populated, zero tickets, all breached, only on_track, tenant isolation (two tenants return different counts)
   - Use `MockRow`/`MockResult` from `tests/unit/conftest.py` for SQL response mocking

4. **Write integration tests** (`tests/integration/test_sla_integration.py` — new file):
   - Use existing fixtures: `db_schema`, `tenant_id`, `async_session`
   - `test_sla_summary_all_categories`: seed 3 breached, 2 at_risk, 5 on_track tickets; assert counts match
   - `test_sla_summary_empty`: no tickets → all counts zero, `total_tickets = 0`
   - `test_sla_summary_tenant_isolation`: seed tickets for two different `tenant_id`s; each query only sees its own
   - Use `TicketService` to create tickets with realistic `response_deadline` values (use past/datetime and future/datetime relative to now to control breach/at_risk state)

## Test Plan
- Unit tests in `tests/unit/test_sla_service.py`: verify `get_sla_summary` logic with mocked SQL responses, covering all three buckets, empty state, and tenant isolation
- Integration tests in `tests/integration/test_sla_integration.py`: verify the full stack (real DB) with seeded tickets at specific deadlines; assert exact count values and tenant scoping

## Acceptance Criteria
- `GET /api/v1/sla/summary` returns `{"success": true, "data": {"breached": N, "at_risk": N, "on_track": N, "total_tickets": N}}` with accurate full-dataset counts
- `breached` count equals the number of open tickets whose `response_deadline < now`
- `at_risk` count equals open tickets with `now < response_deadline <= now + 4h`
- `on_track` count equals all remaining tickets (resolved + open with far deadline)
- Counts are tenant-scoped — a tenant only sees its own tickets
- OpenAPI spec is updated (FastAPI auto-generates it from router decorators)
- Unit tests pass (`pytest tests/unit/test_sla_service.py -v`)
- Integration tests pass (`pytest tests/integration/test_sla_integration.py -v`)
