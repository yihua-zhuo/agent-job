Now I have enough context. Let me write the plan.

# Implementation Plan — Issue #615

## Goal

Create `src/api/routers/ai_chat.py` exposing `POST /api/v1/ai/chat` (accepts message + optional context/conversation_id, returns Chinese reply + suggestions in one request) and `GET /api/v1/ai/sessions` (returns paginated session list for the current user). The router delegates to `AIService` (already present; `ChatService` from #614 provides query helpers but not send/create). No rate limiting, no new ORM models.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0615-add-post-ai-chat-and-get-ai-sessions-router-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0615-add-post-ai-chat-and-get-ai-sessions-router-endpoints.md`

## Affected Files

- `src/api/routers/ai_chat.py` — **new** — router with `POST /chat` and `GET /sessions`
- `src/main.py` — no changes needed — `iter_routers()` in `src/api/__init__.py` auto-discovers any file exporting a `*_router` name pattern; `ai_chat.py` will be picked up automatically
- `tests/unit/test_ai_chat_router.py` — **new** — unit tests (4+ cases: happy path, auto-create conversation, input validation, sessions pagination + boundary)
- `tests/integration/test_ai_chat_integration.py` — **new** — integration tests against real PostgreSQL (3 cases: send+reply, sessions list, pagination)

## Implementation Steps

**Step 1: Create `src/api/routers/ai_chat.py`**

Define `ai_chat_router` (prefix `/api/v1/ai`, same prefix as `ai_router` — distinct paths prevent collision). Import `ChatRequest`, `ChatResponse` from `src/models/ai.py` and `AIService` from `src/services/ai_service.py`. Copy the `_success` and `_paginated_response` helpers from `ai.py` (lines 34–65). Implement two endpoints:

- `POST /chat` — if `request.conversation_id` is None, call `AIService.create_conversation`, then call `AIService.send_message`. Wrap result in `ChatResponse.to_dict()` inside `_success`. No rate limiting (issue requirement).
- `GET /sessions` — call `AIService.list_conversations(tenant_id, user_id, page, page_size)`, serialize each conversation model via `.to_dict()`, return `_paginated_response`.

```python
# src/api/routers/ai_chat.py
"""AI Chat router — /api/v1/ai/chat and /api/v1/ai/sessions endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.ai import ChatRequest, ChatResponse
from services.ai_service import AIService

ai_chat_router = APIRouter(prefix="/api/v1/ai", tags=["ai-chat"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@ai_chat_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AIService(session)
    if request.conversation_id is None:
        conversation = await svc.create_conversation(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id, title=None
        )
        conversation_id = conversation.id
    else:
        conversation_id = request.conversation_id
    result = await svc.send_message(
        conversation_id=conversation_id,
        message=request.message,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
    )
    response = ChatResponse(
        reply=result.reply,
        suggestions=result.suggestions,
        actions=result.actions,
    )
    return _success(response.to_dict(), message=result.reply or "")


@ai_chat_router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AIService(session)
    conversations, total = await svc.list_conversations(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        page=page,
        page_size=page_size,
    )
    return _paginated_response(
        items=[c.to_dict() for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )
```

**Step 2: Verify router auto-registration**

Confirm `iter_routers()` in `src/api/__init__.py` will discover `ai_chat_router` (the name matches the `*_router` suffix rule on line 39). No change to `src/main.py` is required.

**Step 3: Run linter**

`ruff check src/api/routers/ai_chat.py` → 0 errors

**Step 4: Create `tests/unit/test_ai_chat_router.py`**

Mirror the pattern from `tests/unit/test_ai_router.py`. Use the same `client_with_service` fixture approach: monkeypatch `AIService` onto the router module, override `require_auth` and `get_db` dependencies, use `TestClient(raise_server_exceptions=False)`. Tests:

1. `POST /chat` with `conversation_id` provided — `send_message` called with correct args, reply returned
2. `POST /chat` without `conversation_id` — `create_conversation` called first, then `send_message`
3. `POST /chat` with empty `message` — expects 422 (Pydantic `min_length=1` on `ChatRequest.message`)
4. `GET /sessions` — `list_conversations` called with correct tenant/user, paginated items + total returned
5. `GET /sessions` boundary — `page=0` → 422, `page_size=101` → 422 (both validated by `Query(ge=1)` / `Query(le=100)`)

**Step 5: Create `tests/integration/test_ai_chat_integration.py`**

Use `db_schema`, `tenant_id`, `async_session` fixtures. Requires `_seed_tenant` (same as `test_ai_integration.py`). Tests:

1. `POST /chat` (no conversation_id) — creates conversation, stores user+assistant messages, returns reply
2. `POST /chat` (with conversation_id) — continues existing conversation
3. `GET /sessions` — after step 1, `sessions` returns items including the created session, total ≥ 1
4. `GET /sessions` with pagination — `page=1&page_size=5` returns correct shape

## Test Plan

- Unit tests in `tests/unit/`: `test_ai_chat_router.py` — covers happy path, auto-conversation creation, Pydantic validation (422), sessions pagination, query boundary validation
- Integration tests in `tests/integration/`: `test_ai_chat_integration.py` — real DB via `async_session`, verifies end-to-end router → service → DB round-trip for both endpoints
- Dev-plan verification:
  - `ruff check src/api/routers/ai_chat.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_ai_chat_router.py -v` → ≥ 4 passed
  - `PYTHONPATH=src pytest tests/integration/test_ai_chat_integration.py -v` → all passed (requires `DATABASE_URL`)
  - Manual E2E: `POST /api/v1/ai/chat` returns `{"success": true, "data": {"reply": "...", "suggestions": [...]}}`; `GET /api/v1/ai/sessions` returns paginated `{items, total, page, page_size, total_pages}`

## Acceptance Criteria

- `ruff check src/api/routers/ai_chat.py` exits 0 with no errors
- `POST /api/v1/ai/chat` with `{"message": "你好"}` returns HTTP 200 with `{"success": true, "data": {"reply": "...", "suggestions": [...]}}`
- `POST /api/v1/ai/chat` with `{"message": ""}` returns HTTP 422 (Pydantic `min_length=1` enforcement)
- `GET /api/v1/ai/sessions?page=1&page_size=20` returns HTTP 200 with `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20, "total_pages": M}}`
- `GET /api/v1/ai/sessions?page=0` returns HTTP 422; `GET /api/v1/ai/sessions?page_size=101` returns HTTP 422
- `PYTHONPATH=src pytest tests/unit/test_ai_chat_router.py -v` → ≥ 4 passed
- `PYTHONPATH=src pytest tests/integration/test_ai_chat_integration.py -v` → all passed
- Multi-tenant isolation: session from tenant A is not visible in tenant B's `GET /sessions` response
