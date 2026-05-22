# Implementation Plan — Issue #577

## Goal
Define Pydantic request/response schemas for AI-generated email and SMS drafts, then implement `AiDraftService` that calls the existing `AIChatGateway` (from issue #41) to produce draft content and suggested actions. No API router is included — this is a pure service-layer task.

## Affected Files
- `src/models/ai_draft.py` — New file: `DraftRequest`, `DraftContext`, `DraftResponse`, and supporting enums
- `src/services/ai_draft_service.py` — New file: `AiDraftService` class
- `src/models/__init__.py` — Add exports for the new schema classes
- `tests/unit/test_ai_draft_service.py` — New file: unit tests for `AiDraftService`
- `tests/integration/test_ai_draft_service_integration.py` — New file: integration tests for `AiDraftService`

## Implementation Steps

1. **Create `src/models/ai_draft.py`** with:
   - `TemplateType(strEnum)` with values `EMAIL`, `SMS`
   - `DraftType(strEnum)` with values `EMAIL`, `SMS`
   - `ToneType(strEnum)` with values `PROFESSIONAL`, `FRIENDLY`, `URGENT`
   - `DraftContext(BaseModel)`: `customer_id: int`, `opportunity_id: int | None`, `template_type: TemplateType`
   - `DraftRequest(BaseModel)`: `type: DraftType`, `subject: str | None` (required only when `type=EMAIL`), `tone: ToneType`, `context: DraftContext`
   - `SuggestedAction(BaseModel)`: `label: str`, `action_type: str`, `payload: dict`
   - `DraftResponse(BaseModel)`: `body: str`, `suggested_actions: list[SuggestedAction]`, `to_dict() -> dict`
   - Add `to_dict()` method to `DraftResponse` following the same pattern as `ChatResponse` in `ai.py`

2. **Update `src/models/__init__.py`** — import and re-export all classes from `ai_draft.py`

3. **Create `src/services/ai_draft_service.py`** following the service pattern from `ai_service.py`:
   - `AiDraftService.__init__(self, session: AsyncSession, gateway: AIChatGateway | None = None)` — store session and gateway (lazy-init if not provided)
   - `async def generate_draft(self, request: DraftRequest, tenant_id: int) -> DraftResponse` — build a prompt from the request fields, call `self.gateway.chat()`, parse the `AIResponse` reply into a `DraftResponse` with `body` and `suggested_actions` (map `AIResponse.actions` to `SuggestedAction` objects), raise `ValidationException` if the gateway returns empty content
   - `async def _build_prompt(self, request: DraftRequest, tenant_id: int) -> list[dict]` — construct the messages list for `AIChatGateway.chat()` with system prompt + user message encoding the draft type, tone, subject (if email), and context fields

4. **Create unit test `tests/unit/test_ai_draft_service.py`**:
   - Fixtures: `mock_db_session` (via `make_mock_session([])`), `ai_draft_service(mock_db_session)`, `draft_request` (a `DraftRequest` fixture)
   - Test `generate_draft` returns a `DraftResponse` with non-empty `body`
   - Test `generate_draft` raises `ValidationException` when gateway returns empty reply
   - Mock `AIChatGateway` in tests that need it via `AiDraftService(mock_db_session, gateway=mock_gateway)`
   - Use `MockState`, `MockRow`, `MockResult` as needed from `conftest.py`

5. **Create integration test `tests/integration/test_ai_draft_service_integration.py`**:
   - Fixtures: `db_schema`, `tenant_id`, `async_session`
   - Use `_seed_customer` / `_seed_opportunity` helpers to populate context data before calling the service
   - Test `generate_draft` with a real session and a real (or test-double) gateway
   - Test error case: call `generate_draft` with a non-existent `customer_id` — `ValidationException` or `NotFoundException` depending on where validation occurs
   - Test `generate_draft` with `opportunity_id` provided and `opportunity_id` omitted

## Test Plan
- Unit tests in `tests/unit/test_ai_draft_service.py`: mock `AIChatGateway`, cover happy path (valid `DraftRequest` → `DraftResponse`), empty-reply error path, subject-required validation for email type
- Integration tests in `tests/integration/test_ai_draft_service_integration.py`: real DB session, real gateway stub, seeded customer/opportunity, verify `DraftResponse.body` is non-empty string and `suggested_actions` is a list

## Acceptance Criteria
- `src/models/ai_draft.py` exists and exports `DraftRequest`, `DraftResponse`, `DraftContext`, `SuggestedAction`, and the three enums (`DraftType`, `ToneType`, `TemplateType`)
- `DraftRequest` raises `ValidationException` at model-construct time when `type=EMAIL` and `subject` is absent (Pydantic `model_validator`)
- `AiDraftService(session)` rejects `session=None` (no default argument)
- `AiDraftService.generate_draft` calls `AIChatGateway.chat()` with a non-empty messages list
- `AiDraftService.generate_draft` returns a `DraftResponse` whose `body` is a non-empty string and `suggested_actions` is a list (possibly empty)
- Unit tests pass with `pytest tests/unit/test_ai_draft_service.py -v`
- Integration tests pass with `pytest tests/integration/test_ai_draft_service_integration.py -v` (requires `DATABASE_URL`)
- `ruff check src/` and `ruff format --check src/` pass with no errors
