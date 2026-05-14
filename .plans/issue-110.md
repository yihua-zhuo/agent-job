Now I have a thorough picture of the codebase. Let me write the implementation plan.

# Implementation Plan — Issue #110

## Goal

Add a backend AI Chat Assistant API (`POST /api/v1/ai/chat`, `POST /api/v1/ai/conversation`, `GET /api/v1/ai/conversation/{id}`) so the frontend `/ai` page can send messages to an AI assistant with full CRM context (customers, tickets, opportunities, tasks). No AI gateway or `claw` wrapper exists yet; a stub adapter is included that can be swapped for a real MiniMax-M2.7 call later.

## Affected Files

- `src/db/models/ai_conversation.py` — **new** ORM model for conversations and messages
- `src/db/models/__init__.py` — re-export `AIConversationModel`, `AIMessageModel`
- `src/api/__init__.py` — export `ai_router`
- `src/main.py` — `app.include_router(ai_router)`
- `alembic/env.py` — import `AIConversationModel`, `AIMessageModel` so `--autogenerate` sees them
- `src/internal/ai_gateway.py` — **new** async adapter (stub) wrapping the AI gateway call
- `src/services/ai_service.py` — **new** `AIService` with conversation CRUD and CRM-context injection
- `src/api/routers/ai.py` — **new** `ai_router` with the three endpoints
- `src/models/ai.py` — **new** Pydantic request/response schemas for the router
- `tests/unit/test_ai_service.py` — **new** unit tests for `AIService` (mock session, mock AI gateway)
- `tests/unit/test_ai_router.py` — **new** unit tests for `ai_router` endpoints (TestClient + mocked service)
- `tests/integration/test_ai_integration.py` — **new** integration tests (real DB, real session)

## Implementation Steps

1. **Create `src/db/models/ai_conversation.py`** — two SQLAlchemy ORM models:
   - `AIConversationModel`: `id`, `tenant_id`, `user_id`, `title`, `created_at`, `updated_at`; `__tablename__ = "ai_conversations"`, `index=True` on `(tenant_id, user_id)`
   - `AIMessageModel`: `id`, `conversation_id`, `tenant_id`, `role` (`"user"|"assistant"`), `content` (`Text`), `created_at`; `index=True` on `(tenant_id, conversation_id)`
   - Both have `to_dict()` methods and inherit from `db.base.Base`

2. **Register models** — add `AIConversationModel` and `AIMessageModel` to `src/db/models/__init__.py`; add both imports to `alembic/env.py`

3. **Create `src/internal/ai_gateway.py`** — an async `AIChatGateway` class with a `chat(messages, context)` method. Initially returns a realistic mock reply (deterministic based on input hash so tests are stable). The class is structured so swapping in a real MiniMax-M2.7 call only requires changing the inner `_call_gateway` method — no call sites need updating.

4. **Create `src/models/ai.py`** — Pydantic `BaseModel` schemas:
   - `ChatRequest`: `message: str = Field(..., min_length=1, max_length=4000)`, `context: dict | None = Field(default=None)`
   - `ChatResponse`: `reply: str`, `suggestions: list[str] | None`, `actions: list[dict] | None`
   - `CreateConversationRequest`: `title: str | None = Field(default=None, max_length=200)`
   - `ConversationResponse`: `id: int`, `title: str`, `created_at: str`, `updated_at: str`
   - `MessageResponse`: `id: int`, `role: str`, `content: str`, `created_at: str`
   - `ConversationDetailResponse`: includes `messages: list[MessageResponse]`

5. **Create `src/services/ai_service.py`** — `AIService(session: AsyncSession)` with methods:
   - `send_message(conversation_id, message, tenant_id, user_id) -> ChatResponse` — stores user message, calls `AIChatGateway.chat()` with CRM-enriched context (customer/ticket/opportunity summaries fetched from the session), stores assistant reply, returns `ChatResponse`
   - `create_conversation(tenant_id, user_id, title) -> AIConversationModel`
   - `get_conversation(conversation_id, tenant_id) -> AIConversationModel` — raises `NotFoundException`
   - `list_conversations(tenant_id, user_id, page, page_size) -> tuple[list[AIConversationModel], int]`
   - `get_conversation_messages(conversation_id, tenant_id, limit) -> list[AIMessageModel]`
   - `_enrich_context(tenant_id, user_id) -> dict` — private helper that queries `CustomerModel`, `TicketModel`, `OpportunityModel`, `ActivityModel`, `TaskModel` and returns a structured context dict injected into the AI gateway prompt

6. **Create `src/api/routers/ai.py`** — `ai_router = APIRouter(prefix="/api/v1/ai", tags=["ai"])` with:
   - `POST /chat` — body `ChatRequest`, returns `ChatResponse`; if `conversation_id` is absent in request body, creates a new conversation first (stateless convenience); calls `AIService(session).send_message(...)`
   - `POST /conversation` — body `CreateConversationRequest`, returns `ConversationResponse` with `status_code=201`
   - `GET /conversation/{conversation_id}` — returns `ConversationDetailResponse` with paginated messages
   - All endpoints: `ctx: AuthContext = Depends(require_auth)`, `session: AsyncSession = Depends(get_db)`
   - Rate limiting: simple in-memory `defaultdict[int, list[float]]` keyed by `tenant_id`; if more than 30 requests arrive within a 60-second sliding window, raise `ValidationException("Rate limit exceeded")`
   - Request/response envelopes: `{"success": True, "data": {...}}`

7. **Wire router into app** — add `ai_router` import to `src/api/__init__.py` and call `app.include_router(ai_router)` in `src/main.py` alongside the other routers

8. **Add unit tests** — `tests/unit/test_ai_service.py`: mock `AsyncSession`, mock `AIChatGateway`, test `send_message` (happy path + raises `NotFoundException` for missing conversation), test `create_conversation`, test `get_conversation` (404), test `list_conversations` (pagination); `tests/unit/test_ai_router.py`: TestClient pattern mirroring `test_customers_router.py` — override `require_auth` and `get_db`, monkeypatch `AIService`, cover all three endpoints plus rate-limit rejection

9. **Add integration test** — `tests/integration/test_ai_integration.py`: uses `db_schema`, `tenant_id`, `async_session` fixtures; creates a conversation, sends a message, verifies it is persisted and retrievable; tests 404 for missing conversation_id

10. **Run alembic migration** — generate `alembic/versions/<id>_add_ai_conversations.py` following the CLAUDE.md workflow (spin up `alembic_dev` DB, run `alembic upgrade head`, `alembic revision --autogenerate`, review, apply, verify empty diff, delete empty revision)

## Test Plan

- Unit tests in `tests/unit/`:
  - `test_ai_service.py` — AIService business logic (mock session + mock AI gateway)
  - `test_ai_router.py` — all three endpoints, validation errors, 404, rate-limit exceeded (mocked service layer)
- Integration tests in `tests/integration/`:
  - `test_ai_integration.py` — real DB: create conversation → send message → retrieve messages, plus 404 case

## Acceptance Criteria

- `POST /api/v1/ai/chat` accepts `{ "message": "..." }` and returns `{ "reply": "...", "suggestions": [...], "actions": [...] }` with `success: true`
- `POST /api/v1/ai/conversation` creates a new conversation and returns its `id` and `created_at`
- `GET /api/v1/ai/conversation/{id}` returns conversation metadata plus its message list
- Conversation history is tenant-scoped — a conversation from tenant A is not accessible to tenant B
- The AI gateway adapter is injectable (mock works in unit tests, real implementation can replace it without changing service code)
- OpenAPI spec at `/openapi.json` includes the three new paths after the router is registered
- All tests pass: `pytest tests/unit/test_ai_service.py tests/unit/test_ai_router.py tests/integration/test_ai_integration.py -v`
