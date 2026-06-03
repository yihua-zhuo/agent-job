Now I have full context. The dev-plan contract is clear, the ChatService exists with real methods (`classify_intent`, `query_customers`, `query_opportunities`, `query_tickets`, `handle_message`), and the conftest pattern is well-understood. The plan must match the actual ChatService API, not the dev-plan's hypothetical `get_active_conversation` / `build_context_dict` (which don't exist in the real code).

# Implementation Plan — Issue #616

## Goal
Add `tests/unit/test_chat_service.py` covering `ChatService.classify_intent` (all 4 intent branches + empty-input validation) and the three `query_*` helpers (`query_customers`, `query_opportunities`, `query_tickets`), plus `handle_message` routing, using the existing `make_mock_session` infrastructure with newly-added `make_customer_handler` / `make_opportunity_handler` / `make_ticket_handler` mocks in `conftest.py` — no real DB.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0616-add-unit-tests-for-chatservice-intent-detection-and-query-he.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0616-add-unit-tests-for-chatservice-intent-detection-and-query-he.md`

**Reality check** (code-grounded): The actual `ChatService` at `src/services/chat_service.py` exposes:
- `classify_intent(text) -> Intent` where `Intent = Literal["customer_lookup", "sales_summary", "ticket_query", "general"]` — **4** branches, not the 6 mentioned in the dev-plan.
- `query_customers(tenant_id, keyword, limit) -> list[dict]`
- `query_opportunities(tenant_id, keyword, limit) -> list[dict]`
- `query_tickets(tenant_id, keyword, status, limit) -> list[dict]`
- `handle_message(text, tenant_id) -> dict`

The dev-plan's hypothetical `get_active_conversation` / `build_context_dict` do **not** exist in the real code. This plan tests what is actually there.

## Affected Files
- `tests/unit/conftest.py` — add three stateful domain handlers (`make_customer_handler`, `make_opportunity_handler`, `make_ticket_handler`) that return a dict of `{"execute": callable}` mapped to `make_mock_session`. These mirror the existing `tests/unit/domain_handlers/customers.py` pattern but are re-exported at conftest scope for use by `test_chat_service.py` only.
- `tests/unit/test_chat_service.py` — new file, ~200 lines, four test classes.

## Implementation Steps

1. **Verify the existing domain handler pattern in `tests/unit/domain_handlers/customers.py`** — read the file to confirm the `get_handlers(state) -> list[dict]` convention and that each handler dict has an `execute(sql, params)` callable that matches SQL fragments. (No code change here, just confirm shape.)

2. **Add `make_customer_handler(state)`, `make_opportunity_handler(state)`, `make_ticket_handler(state)` to `tests/unit/conftest.py`** — each returns a `dict` with an `"execute"` key whose value is a closure accepting `(sql: str, params: dict | None)` and returning a `MockResult`. Each handler:
   - Seeds its respective `MockState` attribute (e.g. `state.customers`, `state.opportunities`, `state.tickets`) with a single test row when called for the first time.
   - Matches `SELECT ... FROM <table>` (lowercased) and returns a `MockResult([MockRow(row)])` when `tenant_id` in params matches the seeded row.
   - Returns `MockResult([])` (or `None` to let the dispatcher fall through) for non-matching SQL.
   - Keep handler implementations stateless beyond the one-time row insertion; the test asserts on the returned dict structure, not on handler internals.

3. **Update `MockState` in `tests/unit/conftest.py`** — add `self.opportunities: dict[int, dict] = {}`, `self.opportunities_next_id: int = 1`, `self.tickets: dict[int, dict] = {}`, `self.tickets_next_id: int = 1` to the existing class. The `customers` attribute already exists from prior handlers.

4. **Create `tests/unit/test_chat_service.py`** with the following structure:

   - **Module-level imports**: `pytest`, `pytest.raises`, `from services.chat_service import ChatService`, `from tests.unit.conftest import MockState, make_mock_session, make_customer_handler, make_opportunity_handler, make_ticket_handler`, `from pkg.errors.app_exceptions import ValidationException`.

   - **`mock_db_session` fixture**: instantiates `MockState()`, calls `make_mock_session([make_customer_handler(state), make_opportunity_handler(state), make_ticket_handler(state)], state=state)`.

   - **`chat_service` fixture**: returns `ChatService(mock_db_session)`.

   - **`class TestClassifyIntent`**: 
     - Parametrized test `test_classify_intent_returns_correct_intent(message, expected)` with 5 cases:
       - `("I need help with a support ticket", "ticket_query")` — regex matches `ticket`/`support`
       - `("Show me the sales pipeline forecast", "sales_summary")` — regex matches `pipeline`/`forecast`
       - `("Find customer by name", "customer_lookup")` — regex matches `customer`
       - `("What is the weather today", "general")` — no match, falls through
       - `("How are you doing", "general")` — no keyword hit, falls through
     - `test_classify_intent_raises_on_empty_text`: `pytest.raises(ValidationException)` for `""` and `"   "`.
     - `test_classify_intent_first_match_wins`: assert `classify_intent("customer support ticket")` returns `"customer_lookup"` (the first regex in `_INTENT_REGEX_PATTERNS` to match).

   - **`class TestQueryHelpers`**:
     - `test_query_customers_returns_list_of_dicts`: seed one customer via `mock_db_session._state.customers[1] = {"id": 1, "tenant_id": 1, "name": "Alice", "email": "a@x.com", "created_at": "2026-01-01"}`; call `await chat_service.query_customers(tenant_id=1)`; assert `isinstance(result, list) and len(result) >= 0` and each element is a `dict`.
     - `test_query_customers_with_keyword`: same seed; call `query_customers(tenant_id=1, keyword="Alice")`; assert result is a list.
     - `test_query_customers_raises_on_invalid_limit`: `pytest.raises(ValidationException)` for `limit=0` and `limit=201`.
     - `test_query_opportunities_returns_list_of_dicts`: seed one opportunity; call; assert list-of-dicts shape.
     - `test_query_opportunities_with_digit_keyword`: seed one opportunity; call with `keyword="42"`; assert no exception.
     - `test_query_opportunities_raises_on_invalid_limit`: same pattern.
     - `test_query_tickets_returns_list_of_dicts`: seed one ticket; call; assert list-of-dicts shape.
     - `test_query_tickets_with_status_filter`: seed one ticket with `status="open"`; call with `status="closed"`; assert result is empty list (or appropriate empty match).
     - `test_query_tickets_raises_on_invalid_limit`: same pattern.

   - **`class TestHandleMessage`**:
     - `test_handle_message_customer_intent`: call with `"Find customer John"`; assert returned dict has keys `{"intent", "query_results", "error"}` and `intent == "customer_lookup"`.
     - `test_handle_message_general_intent`: call with `"Hello there"`; assert `intent == "general"` and `query_results is None`.
     - `test_handle_message_empty_text`: call with `""`; assert `intent == "general"` and `error == "empty message"`.
     - `test_handle_message_whitespace_text`: call with `"   "`; assert same empty-message branch.

5. **Run `ruff check tests/unit/conftest.py tests/unit/test_chat_service.py`** — fix any lint errors.

6. **Run the full test file** to confirm all test cases pass.

## Test Plan
- **Unit tests in `tests/unit/`**: New `tests/unit/test_chat_service.py` (~200 lines, ≥ 14 test cases covering classify_intent branches + query helper validation + handle_message routing).
- **Integration tests in `tests/integration/`**: None — the dev-plan explicitly excludes integration tests (no real DB).
- **Dev-plan verification**:
  - `ruff check tests/unit/conftest.py tests/unit/test_chat_service.py` → 0 errors (maps to board §6 line 1).
  - `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → all passed, 0 failed (maps to board §6 lines 2–3).
  - `git status` → no changes in `alembic/versions/` (maps to board §6 line 4).
  - `ruff check tests/unit/conftest.py` → 0 errors (maps to board §6 line 5).

## Acceptance Criteria
- `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` shows ≥ 14 passed and 0 failed.
- `ruff check tests/unit/conftest.py tests/unit/test_chat_service.py` exits 0.
- All 4 `Intent` literal values (`customer_lookup`, `sales_summary`, `ticket_query`, `general`) are covered by at least one test case in `TestClassifyIntent`.
- `classify_intent` raises `ValidationException` for empty/whitespace input (verified via `pytest.raises`).
- All three `query_*` methods return `list[dict]` and raise `ValidationException` when `limit` is out of range.
- `handle_message` returns the correct `{"intent", "query_results", "error"}` envelope for customer-intent, general-intent, and empty-text inputs.
- No new files in `alembic/versions/`; no changes to `src/services/chat_service.py` or any ORM model.

## Risks / Open Questions
- **Dev-plan §3.3 mentions "≥ 6 intent classification cases"** but the real `ChatService` only has 4 `Intent` values. The test file will cover all 4 real branches plus empty-input validation, totaling ≥ 6 distinct test cases when counting the `pytest.raises` validations separately. This is a documentation drift in the dev-plan, not a code issue.
- **Dev-plan §2.1 references `get_active_conversation` and `build_context_dict`** that do not exist in `src/services/chat_service.py`. Those will not be tested; the real `query_customers` / `query_opportunities` / `query_tickets` / `handle_message` methods are the query helpers that warrant coverage.
- **`MockState.opaque` vs new dedicated attributes**: The board suggests using `state.opaque['chat_sessions']` but adding dedicated `state.opportunities` / `state.tickets` dicts (mirroring the existing `state.customers`) is simpler and follows the same pattern other domain handlers already use in this codebase.
