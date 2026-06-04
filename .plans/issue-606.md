I have all the information needed. Here is the implementation plan:

# Implementation Plan — Issue #606

## Goal
Add a `GET /tickets/categorization/metrics` endpoint that returns aggregated accuracy metrics for the LLM-based ticket categorization system. The endpoint exposes total categorized count, human override count/rate, average confidence, and breakdowns by category_type and priority, all scoped to the authenticated tenant. This enables dashboards/reporting to quantify categorization quality.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0606-add-accuracy-metrics-endpoint-and-basic-reporting.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0606-add-accuracy-metrics-endpoint-and-basic-reporting.md`

## Affected Files
- `src/services/ticket_categorization_service.py` — **new file**: add `get_metrics(tenant_id)` method that runs three SQL aggregations (overall, by `category_type`, by `priority`) against `TicketCategorizationModel` and returns a `dict` with `total_categorized`, `override_count`, `override_rate`, `average_confidence`, `by_type`, `by_priority`.
- `src/api/routers/tickets.py` — append `GET /tickets/categorization/metrics` endpoint after line 496 (after `patch_categorization_feedback`). The import `from services.ticket_categorization_service import TicketCategorizationService` already exists at line 16. Follow the same `tickets_router` + `Depends(require_auth)` + `Depends(get_db)` pattern used by `get_sla_summary` at lines 458–470.
- `tests/unit/test_ticket_categorization_metrics.py` — **new file**: unit tests for `TicketCategorizationService.get_metrics()` covering happy path, empty result (zero division guard), and NULL confidence (coalesce guard).
- `tests/unit/test_tickets_router.py` — add a `test_get_categorization_metrics` function (appended after line 815) using the existing `client_with_service` fixture pattern (see the `test_*_sla_summary` pattern at lines 760–815) that patches `TicketCategorizationService.get_metrics` and asserts the JSON envelope.

## Implementation Steps

1. **Add `get_metrics` method to `TicketCategorizationService` in `src/services/ticket_categorization_service.py`**
   - The file already exists; append the method to the existing `TicketCategorizationService` class.
   - `__init__` already takes `session: AsyncSession` with no default — do not change.
   - Run three queries, all `WHERE tenant_id = :tenant_id`:
     - **Overall**: `func.count(id)`, `func.coalesce(func.avg(confidence), 0.0)`, `func.sum(case((human_override == True, 1), else_=0))`.
     - **By category_type**: same three aggregations, `.group_by(category_type)`.
     - **By priority**: same three aggregations, `.group_by(priority)`.
   - Compute `override_rate = override_count / total if total > 0 else 0.0` in Python (avoid `None`/division).
   - Return `dict` with keys: `total_categorized` (int), `override_count` (int), `override_rate` (float, 4 dp), `average_confidence` (float, 4 dp), `by_type` (dict keyed by category_type string), `by_priority` (dict keyed by priority string). Each breakdown value is a dict `{count, avg_confidence, overrides}`.
   - Do **not** call `.to_dict()` — there is no ORM object to serialize; return a plain dict (matches dev-plan §4.1).
   - Do **not** raise `AppException` for empty results — return zeros.

2. **Add `GET /tickets/categorization/metrics` endpoint to `src/api/routers/tickets.py`**
   - Append after the last existing endpoint (`patch_categorization_feedback` at line 496).
   - Use the same dependency pattern as `get_sla_summary`:
     ```python
     @tickets_router.get("/tickets/categorization/metrics")
     async def get_categorization_metrics(
         ctx: AuthContext = Depends(require_auth),
         session: AsyncSession = Depends(get_db),
     ):
         """Return categorization accuracy metrics for the current tenant."""
         svc = TicketCategorizationService(session)
         metrics = await svc.get_metrics(tenant_id=ctx.tenant_id or 0)
         return {"success": True, "data": metrics}
     ```
   - `tickets_router` is defined with `prefix="/api/v1"` (line 20), so the full path is `/api/v1/tickets/categorization/metrics` — matches the dev-plan.
   - The import for `TicketCategorizationService` already exists at line 16 — no new import needed.

3. **Create `tests/unit/test_ticket_categorization_metrics.py`**
   - Define `MockResult` (with `.one()`) and `MockScalarResult` (with `.all()`) helpers locally — do not import from `tests/unit/conftest.py` (keep the test self-contained, matching the dev-plan example).
   - Use `AsyncMock` for the session. Set up a `side_effect` list of three return values for the three sequential `session.execute()` calls (overall, by_type, by_priority).
   - **Test 1 — `test_get_metrics_returns_structure`**: assert all six top-level keys present, `override_rate` is a float, `by_type` / `by_priority` are dicts.
   - **Test 2 — `test_get_metrics_empty_result`**: mock `total=0`, `override_count=0`, `avg_confidence=None`; assert `override_rate == 0.0`, `total_categorized == 0`, `average_confidence == 0.0` (coalesce).
   - **Test 3 — `test_get_metrics_null_confidence_defaults_to_zero`**: mock overall row with `avg_confidence=None` and total > 0; assert `average_confidence == 0.0`.
   - All tests pass `tenant_id=1` — verify the WHERE clause is applied by checking the session mock receives a SQLAlchemy `select` with the tenant filter (assertion optional; the main contract is correct return shape).

4. **Append `test_get_categorization_metrics` to `tests/unit/test_tickets_router.py`**
   - Follow the pattern from the `test_requires_auth` (line 800) and the SLA summary tests (lines 760–798) in the same file.
   - Use the existing `client_with_service` fixture (line 111) which already wires up a mock `TicketCategorizationService` — or monkeypatch `api.routers.tickets.TicketCategorizationService` directly.
   - Mock `TicketCategorizationService.get_metrics` with `AsyncMock(return_value=mock_metrics_dict)`.
   - Assert `response.status_code == 200`, `data["success"] is True`, and all expected fields are present in `data["data"]`.

## Test Plan
- Unit tests in `tests/unit/`:
  - **New: `tests/unit/test_ticket_categorization_metrics.py`** — 3 tests for `TicketCategorizationService.get_metrics()`: structure shape, empty-result zero-division guard, NULL-confidence coalesce guard. All use `AsyncMock` for the session, no DB.
  - **Modified: `tests/unit/test_tickets_router.py`** — add 1 test `test_get_categorization_metrics` validating the HTTP envelope (`{"success": true, "data": {...}}`) and that `get_metrics` is called with `tenant_id=1`.
- Integration tests in `tests/integration/`: **none** — the dev-plan §5 has no Step for an integration test, and the dev-plan §6 acceptance list does not include one. The dev-plan budget is 0.5–1 day; unit coverage of the service + router is the contract.
- Dev-plan verification (from §6 acceptance):
  1. `ruff check src/services/ticket_categorization_service.py` → 0 errors
  2. `ruff check src/api/routers/tickets.py` → 0 errors
  3. `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v` → ≥ 3 passed
  4. `PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_get_categorization_metrics -v` → passed
  5. `curl http://localhost:8000/api/v1/tickets/categorization/metrics -H "Authorization: Bearer …"` → 200 with JSON containing all six keys

## Acceptance Criteria
- `GET /api/v1/tickets/categorization/metrics` returns 200 with `{"success": true, "data": {total_categorized, override_count, override_rate, average_confidence, by_type, by_priority}}`.
- All aggregate values are filtered by `tenant_id` derived from the authenticated context.
- When `total_categorized == 0`, `override_rate` is `0.0` (no `ZeroDivisionError`).
- When all `confidence` values are `NULL`, `average_confidence` is `0.0` (coalesce applied at SQL level).
- `ruff check src/services/ticket_categorization_service.py src/api/routers/tickets.py` → 0 errors.
- `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v` → 3 passed.
- `PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_get_categorization_metrics -v` → passed.

## Risks / Open Questions
- **Column name mismatch between dev-plan code and actual model.** The dev-plan's Step 1 example code references `TicketCategorizationModel.category` and `TicketCategorizationModel.overridden`. The actual model (created by #605 at `src/db/models/ticket_categorization.py:13`) uses `category_type` and `human_override`. The implementation must use the real column names (`category_type` for the type-breakdown `.group_by()`, `human_override` for the override count), not the names in the dev-plan example. The plan uses the real names.
