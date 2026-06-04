Now I have all the verified information. Let me write the implementation plan.

# Implementation Plan — Issue #605

## Goal
Add a `CategorizationFeedbackModel` ORM class to store human overrides for LLM-assigned ticket categorizations, and a `PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` endpoint that records corrections and flags the original `TicketCategorizationModel` as overridden. This enables downstream accuracy measurement (#606) by persisting an auditable trail of every human correction.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0605-add-accuracy-tracking-model-and-feedback-override-endpoint.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0605-add-accuracy-tracking-model-and-feedback-override-endpoint.md`

## Affected Files
- `src/db/models/ticket_categorization.py` — append `CategorizationFeedbackModel` class (table `categorization_feedback`) with `to_dict()` method
- `alembic/versions/<new_rev>_add_categorization_feedback_table.py` — new migration creating `categorization_feedback` table with `tenant_id` index and FK to `tickets.id`
- `src/services/ticket_service.py` — add `submit_categorization_feedback()` method to `TicketService` class
- `src/api/routers/tickets.py` — add `CategorizationFeedbackPayload` Pydantic schema and `PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` endpoint
- `tests/unit/test_ticket_categorization.py` — new file with 3+ test cases for the service method
- `tests/unit/test_tickets_router.py` — add 2 test cases for the PATCH endpoint

## Implementation Steps
1. **Append `CategorizationFeedbackModel` to `src/db/models/ticket_categorization.py` (after L55)**
   - Add a new ORM class mapped to table `categorization_feedback` with columns: `id` (PK, autoincrement), `tenant_id` (Integer, nullable=False, index=True), `ticket_id` (Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True), `original_category` (String(100), nullable=True), `original_priority` (String(50), nullable=True), `corrected_category` (String(100), nullable=True), `corrected_priority` (String(50), nullable=True), `corrected_by` (Integer, nullable=False), `created_at` (DateTime(timezone=True), server_default=func.now(), nullable=False). Include a `to_dict()` method following the same pattern as `TicketCategorizationModel.to_dict()` (L40-L55). Model is append-only audit; no update/delete methods.

2. **Generate Alembic migration for `categorization_feedback`**
   - Follow the exact pattern in `alembic/versions/a0000012_add_ticket_categorization.py`. Run autogenerate against the `alembic_dev` database (per CLAUDE.md Alembic section), manually verify `DateTime(timezone=True)` + `server_default=sa.text('now()')` for `created_at`, verify `ondelete='CASCADE'` FK to `tickets.id`, verify `ix_categorization_feedback_tenant_id` index exists. Write a `downgrade()` that drops the index then the table. Verify three-pass cycle: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all exit 0. Delete any drift-check migration.

3. **Add `submit_categorization_feedback()` to `TicketService` in `src/services/ticket_service.py` (after L255, after `add_reply`)**
   - Add import at top: `from db.models.ticket_categorization import CategorizationFeedbackModel, TicketCategorizationModel`. Add `ValidationException` to the existing `from pkg.errors.app_exceptions import NotFoundException` import.
   - Method signature: `async def submit_categorization_feedback(self, ticket_id: int, tenant_id: int, user_id: int, corrected_category: str | None = None, corrected_priority: str | None = None) -> CategorizationFeedbackModel`
   - Implementation: query `select(TicketCategorizationModel).where(TicketCategorizationModel.ticket_id == ticket_id, TicketCategorizationModel.tenant_id == tenant_id)`. If `scalar_one_or_none()` returns `None`, raise `NotFoundException("TicketCategorization")`. Set `categorization.human_override = True` (the field on the existing model at L31, not `overridden`). Create `CategorizationFeedbackModel(ticket_id=..., tenant_id=..., original_category=categorization.category_type, original_priority=categorization.priority, corrected_category=..., corrected_priority=..., corrected_by=user_id)`. `self.session.add(feedback)`, `await self.session.flush()`, `await self.session.refresh(feedback)`, return `feedback`.

4. **Add Pydantic schema and PATCH endpoint to `src/api/routers/tickets.py`**
   - Add `CategorizationFeedbackPayload` class after the existing Pydantic schemas (after L91, near `TicketBulkUpdate`): `category: str | None = None`, `priority: str | None = None`. Both fields optional to allow partial overrides.
   - Add the PATCH endpoint after `get_sla_summary` (after L464):
     ```python
     @tickets_router.patch("/tickets/{ticket_id}/categorization/feedback")
     async def patch_categorization_feedback(...)
     ```
   - Validate: if both `category` and `priority` are `None`, raise `ValidationException("At least one of category or priority must be provided")`. Call `TicketService(session).submit_categorization_feedback(ticket_id, tenant_id=ctx.tenant_id or 0, user_id=ctx.user_id or 0, corrected_category=body.category, corrected_priority=body.priority)`. Return `{"success": True, "data": feedback.to_dict()}`.

5. **Create unit tests in `tests/unit/test_ticket_categorization.py` (new file)**
   - Use the mock session pattern from `tests/unit/conftest.py` (line 242: `make_mock_session`). Use the domain handler `make_ticket_categorization_handler` from `tests/unit/domain_handlers/ticket_categorization.py` as a template, or use `AsyncMock`/`MagicMock` directly for the session.
   - Test 1 (happy path): pre-seed a `TicketCategorizationModel` in mock state, call `submit_categorization_feedback`, assert `human_override` is `True`, assert a `CategorizationFeedbackModel` row is added with correct `original_category`/`original_priority`/`corrected_category`/`corrected_by`.
   - Test 2 (boundary — no categorization): mock `scalar_one_or_none()` returns `None`, call method, assert `NotFoundException` is raised with `"TicketCategorization"` in detail.
   - Test 3 (error — both fields None in router): import `CategorizationFeedbackPayload`, call the endpoint with `{}`, assert `ValidationException`.

6. **Add router-level tests to `tests/unit/test_tickets_router.py` (after L617 or in `TestCategorizeTicketEndpoint` area ~L474)**
   - Follow the `client_with_service` fixture pattern (L111-L155). Patch `TicketService.submit_categorization_feedback` via `mock_service` (returned at L155 as second tuple element).
   - Test 1: PATCH with `{"category": "technical"}`, mock returns object with `.to_dict()`, assert HTTP 200, `data["success"] is True`, `data["data"]["corrected_category"] == "technical"`.
   - Test 2: PATCH for non-existent ticket, mock raises `NotFoundException`, assert HTTP 404.

## Test Plan
- Unit tests in `tests/unit/`:
  - `tests/unit/test_ticket_categorization.py` (new) — 3 cases: happy path (feedback persisted + `human_override=True`), boundary (no categorization record → `NotFoundException`), error (both fields None → `ValidationException`).
  - `tests/unit/test_tickets_router.py` (modify) — add 2 cases under a new `TestCategorizationFeedbackEndpoint` class: PATCH success (200 + correct envelope), PATCH not found (404 via `NotFoundException`).
- Integration tests in `tests/integration/`: not required by this dev-plan board (KPIs in §1.4 only reference unit tests). The feedback flow is covered by unit tests with mock DB; a full integration test would require a real LLM classification round-trip which is out of scope for #605.
- Dev-plan verification (§6 acceptance):
  - `ruff check src/db/models/ticket_categorization.py src/services/ticket_service.py src/api/routers/tickets.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_ticket_categorization.py -v` → ≥ 3 passed
  - `PYTHONPATH=src pytest tests/unit/test_tickets_router.py::TestCategorizationFeedbackEndpoint -v` → 2 passed
  - `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
  - E2E (manual/optional): `curl -X PATCH http://localhost:8000/api/v1/tickets/1/categorization/feedback -H "Authorization: Bearer ..." -d '{"category": "technical"}'` → `{"success": true, "data": {...}}`

## Acceptance Criteria
- `CategorizationFeedbackModel` exists in `src/db/models/ticket_categorization.py` with columns `id`, `tenant_id`, `ticket_id`, `original_category`, `original_priority`, `corrected_category`, `corrected_priority`, `corrected_by`, `created_at` and a working `to_dict()` method.
- `TicketCategorizationModel.human_override` is set to `True` when feedback is submitted (the field already exists at L31 of the model from #604).
- `PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` endpoint exists, accepts `{"category": str|None, "priority": str|None}`, validates at-least-one-field, persists a `CategorizationFeedbackModel` row, and returns a success envelope.
- Alembic migration creates the `categorization_feedback` table with `tenant_id` index and FK to `tickets.id` with `ondelete=CASCADE`, and is fully reversible.
- All unit tests pass; `ruff check` is clean; migration upgrade/downgrade cycle is clean.
- Service raises `NotFoundException` (not returns an error dict) when no `TicketCategorizationModel` exists for the given ticket.
