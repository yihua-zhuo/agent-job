# Implementation Plan — Issue #507

## Goal
Create `src/api/routers/copilot.py` with two FastAPI endpoints — `POST /copilot/chat` and `GET /copilot/{conversation_id}/history` — using the existing `iter_routers()` auto-discovery (no explicit `src/main.py` change needed), and add unit and integration test coverage. The router delegates to `CopilotService` (from #506) following the project's `{"success": True, "data": ...}` envelope convention.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0507-add-copilotrouter-with-chat-and-history-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0507-add-copilotrouter-with-chat-and-history-endpoints.md`

## Affected Files
- `src/api/routers/copilot.py` — **new** — `CopilotRouter` with two endpoints
- `tests/unit/test_copilot.py` — **new** — unit tests with mocked DB and mocked service
- `tests/integration/test_copilot_integration.py` — **new** — integration tests against real PostgreSQL

## Implementation Steps

1. **Create `src/api/routers/copilot.py` skeleton with stub endpoints.**
   - `POST /copilot/chat` takes `message: str` (query param) and returns `{"success": True, "data": {}}`.
   - `GET /copilot/{conversation_id}/history` returns `{"success": True, "data": {"messages": [], "total": 0}}`.
   - Both use `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`.
   - Router uses `prefix="/copilot", tags=["Copilot"]` so the auto-discovery in `src/api/__init__.py` picks it up automatically via `iter_routers()` — no change to `src/main.py` is required.

2. **Wire `CopilotService` into the chat endpoint.**
   - Add `from services.copilot_service import CopilotService` inside the handler or at module top (safe — no circular import risk).
   - Replace stub with `svc = CopilotService(session)` and call `svc.chat(...)`; `chat()` internally persists the user message, invokes the AI gateway, and persists the assistant reply before returning an `AIResponse`.
   - Return `{"success": True, "data": result}` where `result` is the service's return value.

3. **Wire `CopilotService` into the history endpoint.**
   - Call `svc.get_history(conversation_id, tenant_id=ctx.tenant_id)` directly.
   - Return the service result directly — `get_history()` already applies `.limit(20)` server-side, no slice needed in the router.
   - Return `{"success": True, "data": {"messages": [...], "total": N}}`.

4. **Verify router registers and schema is valid.**
   - Run `ruff check src/api/routers/copilot.py src/main.py`.
   - Run `uvicorn src.main:app --build` or start the app to confirm no import errors and both paths appear in `/openapi.json`.

5. **Write unit tests in `tests/unit/test_copilot.py`.**
   - Use `make_mock_session([])` for an empty mock session.
   - Use `httpx.AsyncClient` with `ASGITransport` and `app.dependency_overrides` to override `get_db`.
   - Mock `services.copilot_service.CopilotService.persist_message` with `unittest.mock.AsyncMock`.
   - Test: `test_chat_returns_envelope` — POST `/copilot/chat?message=hello`, assert `200` and `data["success"] is True`.
   - Test: `test_history_returns_envelope` — GET `/copilot/1/history`, assert `200` and `data["messages"]` is a list.
   - Test: `test_history_caps_at_20` — mock service to return 25 items, assert `len(data["messages"]) == 20`.

6. **Write integration tests in `tests/integration/test_copilot_integration.py`.**
   - Use `@pytest.mark.integration` class `TestCopilotIntegration`.
   - Use `db_schema`, `tenant_id`, and `async_session` fixtures.
   - Seed via `_seed_customer` (from existing helpers) to provide CRM context the service needs.
   - Test: `test_chat_integration` — POST `/copilot/chat?message=hello`, assert `200` with `success: true`.
   - Test: `test_history_integration` — GET `/copilot/{conv_id}/history`, assert `200` with list shape.
   - Test: `test_history_caps_at_20` — seed 25 messages, call endpoint, assert `len(messages) == 20`.

7. **Run full verification suite.**
   - `ruff check src/api/routers/copilot.py` → 0 errors.
   - `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → all passed.
   - `PYTHONPATH=src pytest tests/integration/test_copilot_integration.py -v` → all passed (requires `DATABASE_URL`).
   - Confirm `POST /copilot/chat` and `GET /copilot/{conversation_id}/history` appear in `http://localhost:8000/openapi.json`.

## Test Plan
- Unit tests in `tests/unit/test_copilot.py`: three tests (envelope on chat, envelope on history, 20-message cap), mocked service + mock DB session via `httpx.AsyncClient` transport.
- Integration tests in `tests/integration/test_copilot_integration.py`: three tests against real PostgreSQL, uses existing `db_schema`/`async_session` fixtures.
- Dev-plan verification: the board's §6 maps directly to the commands above; no separate verify script is required.

## Acceptance Criteria
- `ruff check src/api/routers/copilot.py src/main.py` exits 0.
- `uvicorn src.main:app` starts without import errors.
- `POST /copilot/chat` accepts `message` as a query string parameter and returns `{"success": True, "data": {"response": "...", "tool_calls": [...]}}`.
- `GET /copilot/{conversation_id}/history` returns `{"success": True, "data": {"messages": [...], "total": N}}` capped at 20 messages.
- `PYTHONPATH=src pytest tests/unit/test_copilot.py -v` → all passed.
- `PYTHONPATH=src pytest tests/integration/test_copilot_integration.py -v` → all passed (real DB).
- OpenAPI schema contains both endpoints under the `Copilot` tag.