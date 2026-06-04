Now I have full context. The dev-plan contract is clear, the ChatService exists with real methods (`classify_intent`, `query_customers`, `query_opportunities`, `query_tickets`, `handle_message`), and the conftest pattern is well-understood. The plan must match the actual ChatService API, not the dev-plan's hypothetical `get_active_conversation` / `build_context_dict` (which don't exist in the real code).

# Implementation Plan — Issue #616

## Goal
Add `tests/unit/test_chat_service.py` covering `ChatService.classify_intent` (all 4 intent branches + empty-input validation) and the three `query_*` helpers (`query_customers`, `query_opportunities`, `query_tickets`), plus `handle_message` routing, using the existing `make_mock_session` infrastructure with locally-defined mock handlers in the test file — no real DB.

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
- `tests/unit/test_chat_service.py` — new file, ~600 lines, with locally-defined mock handlers and four test classes. No changes to shared `tests/unit/conftest.py`.

## Implementation Steps

1. **Verify the existing `make_mock_session` / `MockState` / `MockResult` API in `tests/unit/conftest.py`** — confirm signatures and import paths. (No code change to conftest.)

2. **Define chat-specific mock handlers locally in `tests/unit/test_chat_service.py`** — `_make_chat_handler(tenant_filter_rows=None)` returns a closure that routes `SELECT ... FROM <table>` by table name fragment (`"from customers"`, `"from opportunities"`, `"from tickets"`) and returns `MockResult` of dict-backed `_MockChatEntity` rows (a local dict-subclass with a `.to_dict()` method). Table-name detection (vs exact SQL text) keeps routing stable across ORM query-form changes. Wrapped by `make_chat_mock_session(tenant_filter_rows=None)`. No `state.opportunities` / `state.tickets` additions to shared `MockState`; tenant seed rows are passed via the `tenant_filter_rows` argument and stored in the local `state.opaque["tenant_filter_rows"]` map.

3. **No changes to shared `MockState`** — tenant-isolated seed data lives in the `tenant_filter_rows` fixture (a plain dict) and the local `state.opaque` slot, keeping conftest untouched.

4. **Create `tests/unit/test_chat_service.py`** with the following structure:

   - **Module-level imports**: `pytest`, `from services.chat_service import ChatService`, `from tests.unit.conftest import MockResult, MockState, make_mock_session`, `from pkg.errors.app_exceptions import ValidationException`. Plus local `_MockChatEntity` dict-subclass with `.to_dict()`, `_customer_dict` / `_opportunity_dict` / `_ticket_dict` row factories, `_make_chat_handler` (table-name routing), and `make_chat_mock_session`.

   - **`mock_db_session` fixture**: calls `make_chat_mock_session()` (no seed rows).

   - **`tenant_filter_rows` fixture**: a plain dict mapping `tenant_id -> {customers: [...], opportunities: [...], tickets: [...]}`, with two tenants seeded.

   - **`seeded_session` fixture**: calls `make_chat_mock_session(tenant_filter_rows)` — used for tests that need cross-entity seeded data.

   - **`class TestClassifyIntent`** (13 tests): one test per regex/keyword branch plus empty/whitespace validation and a keyword-fallback tie-break test.
     - `test_customer_lookup_regex` / `test_ticket_query_regex` / `test_ticket_query_only_ticket_word` — regex hits.
     - `test_sales_summary_regex_deal` / `..._revenue` / `..._pipeline` / `..._opportunity` / `..._forecast` — sales_summary keyword hits.
     - `test_general_no_match` / `test_general_ignores_noise` — no-match fallthrough.
     - `test_empty_text_raises` / `test_whitespace_only_raises` — `ValidationException`.
     - `test_keyword_fallback_tie_uses_first_intent` — verifies keyword-fallback iteration-order rule.

   - **`class TestQueryCustomers`** (8 tests): list-of-dicts, expected keys, tenant isolation, keyword filter, limit validation (zero / negative / > 200), and boundary (limit=200 OK).

   - **`class TestQueryOpportunities`** (8 tests): list-of-dicts, expected keys, keyword filter, numeric keyword matching customer_id, tenant isolation, limit validation.

   - **`class TestQueryTickets`** (8 tests): list-of-dicts, expected keys, keyword filter, status filter, tenant isolation, limit validation.

   - **`class TestHandleMessage`** (7 tests): customer / sales / ticket intents, general intent (no query), empty and whitespace message branches, and result-shape contract (asserts the envelope is a superset of `{"intent", "query_results", "error"}` — not strict equality — so additive changes to the envelope don't break the test).

5. **Run `ruff check tests/unit/test_chat_service.py`** — fix any lint errors.

6. **Run the full test file** to confirm all test cases pass.

## Test Plan
- **Unit tests in `tests/unit/`**: New `tests/unit/test_chat_service.py` (~615 lines, 44 test cases across 5 test classes covering `classify_intent` branches + `query_*` helper validation + `handle_message` routing).
- **Integration tests in `tests/integration/`**: None — the dev-plan explicitly excludes integration tests (no real DB).
- **Dev-plan verification**:
  - `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → all passed, 0 failed.
  - `git status` → no changes in `alembic/versions/`.
  - `ruff check tests/unit/test_chat_service.py` → 0 errors.

## Acceptance Criteria
- `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` shows 44 passed and 0 failed.
- `ruff check tests/unit/test_chat_service.py` exits 0.
- All 4 `Intent` literal values (`customer_lookup`, `sales_summary`, `ticket_query`, `general`) are covered by at least one test case in `TestClassifyIntent`.
- `classify_intent` raises `ValidationException` for empty/whitespace input (verified via `pytest.raises`).
- All three `query_*` methods return `list[dict]` and raise `ValidationException` when `limit` is out of range.
- `handle_message` returns a dict whose keys are a superset of `{"intent", "query_results", "error"}` for customer-intent, sales-intent, ticket-intent, general-intent, empty-text, and whitespace-text inputs.
- No new files in `alembic/versions/`; no changes to `src/services/chat_service.py`, any ORM model, or shared `tests/unit/conftest.py`.

## Risks / Open Questions
- **Dev-plan §3.3 mentions "≥ 6 intent classification cases"** but the real `ChatService` only has 4 `Intent` values. The test file covers all 4 real branches plus 2 empty-input validation tests, totaling 13 cases in `TestClassifyIntent` — well above the dev-plan's 6-case target. This is a documentation drift in the dev-plan, not a code issue.
- **Dev-plan §2.1 references `get_active_conversation` and `build_context_dict`** that do not exist in `src/services/chat_service.py`. Those will not be tested; the real `query_customers` / `query_opportunities` / `query_tickets` / `handle_message` methods are the query helpers that warrant coverage.
- **Local handlers vs shared `tests/unit/domain_handlers/`**: Chat-specific routing is simpler as a local `_make_chat_handler` / `make_chat_mock_session` in the test file because the routing logic (table-name fragment matching) is unique to chat query methods. Reusing the existing `make_customer_handler` / `make_opportunity_handler` / `make_ticket_handler` from `tests/unit/domain_handlers/` would require either generic per-table handlers (overkill) or cross-test-file coupling. The local approach is the right scope for a single-file service test.
