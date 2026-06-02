Now I have a complete picture. Let me write the implementation plan.

# Implementation Plan — Issue #604

## Goal
Wire up `POST /api/v1/tickets/{ticket_id}/categorize` in the tickets router, calling `TicketCategorizationService.categorize_ticket()` and returning the classification result in the standard `ApiResponse` envelope. Also add `auto_categorize_on_create: bool` as a schema field to `TicketCreate` (with the async trigger noted as a future step, not implemented here).

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0604-add-post-tickets-ticket-id-categorize-router-endpoint.md`
Template depth: `medium`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-medium.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0604-add-post-tickets-ticket-id-categorize-router-endpoint.md`

## Affected Files
- `src/api/routers/tickets.py` — Add import for `TicketCategorizationService`, add `auto_categorize_on_create: bool` to `TicketCreate` schema, add `POST /tickets/{ticket_id}/categorize` endpoint
- `tests/unit/test_tickets_router.py` — Add `MockCategorization`, `CATEGORIZATION_ROW`, `TestCategorizeTicketEndpoint` class (3 test cases), update `TestCreateTicketEndpoint` with `auto_categorize_on_create` field

## Implementation Steps

1. **Add import and `auto_categorize_on_create` field to `TicketCreate` schema**  
   In `src/api/routers/tickets.py`, add `from services.ticket_categorization_service import TicketCategorizationService` to the existing imports. Add `auto_categorize_on_create: bool = Field(default=False)` to the `TicketCreate` Pydantic model after `sla_level`.

2. **Add `POST /tickets/{ticket_id}/categorize` endpoint**  
   In `src/api/routers/tickets.py`, after the `auto_assign_ticket` endpoint (~line 346), add the new categorize endpoint that: injects `ctx: AuthContext` and `session: AsyncSession` via `Depends`; constructs `TicketCategorizationService(session)`; calls `svc.categorize_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)`; returns `{"success": True, "data": result.to_dict(), "message": "分类完成"}`. Let `NotFoundException` and `ValidationException` propagate to the global handler (no try/catch in router).

3. **Add `MockCategorization` class and `CATEGORIZATION_ROW` constant to test file**  
   In `tests/unit/test_tickets_router.py`, add a `MockCategorization` class with `__init__(data=None)` and `to_dict()` mirroring `TicketCategorizationModel.to_dict()` (id, tenant_id, ticket_id, category_type, priority, confidence, reasons, suggested_assignee_id, suggested_team, human_override, categorized_at, created_at, updated_at). Add `CATEGORIZATION_ROW` dict with sample values (ticket_id=1, tenant_id=1, category_type="technical", confidence=Decimal("0.85"), etc.).

4. **Add monkeypatch for `TicketCategorizationService` in `client_with_service` fixture**  
   In `tests/unit/test_tickets_router.py`, add `mock_categorization_service = MagicMock()` to the fixture, add `monkeypatch.setattr("api.routers.tickets.TicketCategorizationService", lambda session: mock_categorization_service)` after the existing monkeypatches, and add `mock_categorization_service` to the tuple returned by the fixture so tests can access it.

5. **Add `TestCategorizeTicketEndpoint` class with 3 test cases**  
   After `TestAutoAssignEndpoint` in `tests/unit/test_tickets_router.py`, add:
   - `test_success_returns_200`: mock `mock_categorization_service.categorize_ticket` → return `MockCategorization(CATEGORIZATION_ROW)`; `POST /api/v1/tickets/1/categorize`; assert 200, `body["success"] is True`, `body["data"]["category_type"] == "technical"`
   - `test_not_found_returns_404`: mock `mock_categorization_service.categorize_ticket` → raise `NotFoundException("Ticket")`; `POST /api/v1/tickets/9999/categorize`; assert 404
   - `test_validation_error_returns_422`: mock `mock_categorization_service.categorize_ticket` → raise `ValidationException("AI gateway returned empty response")`; `POST /api/v1/tickets/1/categorize`; assert 422

6. **Add tests for `auto_categorize_on_create` field in `TestCreateTicketEndpoint`**  
   Add two test methods to the existing `TestCreateTicketEndpoint` class in `tests/unit/test_tickets_router.py`:
   - `test_auto_categorize_on_create_field_accepted`: POST with `auto_categorize_on_create: true`; assert 201 (field is accepted, async trigger is a future step — no service call asserted)
   - `test_auto_categorize_on_create_field_default_false`: POST without the field; assert 201 and the field is absent from response data

## Test Plan
- Unit tests in `tests/unit/test_tickets_router.py`: extend existing test file with `MockCategorization`, `CATEGORIZATION_ROW`, `TestCategorizeTicketEndpoint` (3 cases), and 2 cases for `auto_categorize_on_create` in `TestCreateTicketEndpoint`
- Integration tests in `tests/integration/`: none required — `TicketCategorizationService` already has integration tests in `tests/unit/test_ticket_categorization_service.py`; router is tested via unit test with mock service
- Dev-plan verification: The target board has no `§6` commands (board document ends after §4). Per operational rule "run the corresponding machine-checkable verification from §6 when available", the applicable verification is `PYTHONPATH=src pytest tests/unit/test_tickets_router.py -v` which should show all new and existing tests pass (target: ≥ 3 new passed)

## Acceptance Criteria
- `ruff check src/api/routers/tickets.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_tickets_router.py -v` → all tests pass (existing + new)
- `POST /api/v1/tickets/{ticket_id}/categorize` → 200 with `{"success": true, "data": {"category_type": ..., "confidence": ..., ...}, "message": "分类完成"}`
- `POST /api/v1/tickets/{ticket_id}/categorize` on non-existent ticket → 404 (`NotFoundException` caught globally)
- `TicketCreate` schema accepts `auto_categorize_on_create: bool` field (default `false`) without breaking existing create tests
- Async trigger for `auto_categorize_on_create=true` is documented as deferred (no behavior change in this step)
