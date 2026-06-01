Now I have enough context. Let me write the implementation plan.

---

# Implementation Plan — Issue #614

## Goal
Create `src/services/chat_service.py` providing a `ChatService` class with keyword/regex intent classification (`customer_lookup | sales_summary | ticket_query | general`) and three DB query helpers (`query_customers`, `query_opportunities`, `query_tickets`) that filter by `tenant_id` and return ORM model instances. This is pure service-layer infrastructure with no router changes.

## Source Contract

Dev-plan target: `docs/dev-plan/50-automation/0614-add-chatservice-with-intent-classification-and-db-query-help.md`
Template depth: `deep`
Reading order followed:
1. `docs/dev-plan/README.md`
2. `docs/dev-plan/_template-deep.md`
3. `docs/dev-plan/50-automation/0614-add-chatservice-with-intent-classification-and-db-query-help.md`

## Affected Files

- `src/services/chat_service.py` — **new** — `ChatService` with `classify_intent`, `query_customers`, `query_opportunities`, `query_tickets`, and `handle_message`
- `tests/unit/test_chat_service.py` — **new** — unit tests covering all 4 intent paths, all 3 helpers, and error/edge cases
- `src/db/models/customer.py` — read-only (ORM model the service queries)
- `src/db/models/opportunity.py` — read-only (ORM model the service queries)
- `src/db/models/ticket.py` — read-only (ORM model the service queries)
- `src/pkg/errors/app_exceptions.py` — read-only (source of `NotFoundException`, `ValidationException`)
- `tests/unit/domain_handlers/customers.py` — read-only (pattern reference for mock handler in tests)
- `tests/unit/domain_handlers/sales.py` — read-only (pattern reference for opportunity mock handler)
- `tests/unit/domain_handlers/tickets.py` — read-only (pattern reference for ticket mock handler)

## Implementation Steps

1. **Create `src/services/chat_service.py` — skeleton class**  
   - Define file with imports (`AsyncSession`, `Literal`, `re`, `NotFoundException`, `ValidationException`)
   - Define module-level `Intent = Literal["customer_lookup", "sales_summary", "ticket_query", "general"]`
   - Define `_INTENT_REGEX_PATTERNS` and `_INTENT_KEYWORD_MAP` constants at module level
   - Implement `ChatService.__init__(self, session: AsyncSession)` — store session, no None default
   - Add stub async method signatures for `classify_intent`, `query_customers`, `query_opportunities`, `query_tickets`, `handle_message`
   - **Verify**: `ruff check src/services/chat_service.py` → 0 errors

2. **Implement `classify_intent`**   - Regex-first: iterate `_INTENT_REGEX_PATTERNS` in order (customer_lookup → ticket_query → sales_summary), return match on first hit
   - Keyword fallback (longest-match wins): iterate `_INTENT_KEYWORD_MAP`, no match → `"general"`
   - Guard empty/whitespace-only text with `ValidationException("text cannot be empty")`
   - **Verify**: `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k classify` → all passed

3. **Implement `query_customers`**  
   - Guard `limit <= 0 or limit > 200` → `ValidationException`
   - Build conditions list: `CustomerModel.tenant_id == tenant_id`, then if `keyword` present → ILIKE on `name` and `email` with escaped `%` / `_` / `\`
   - `select(CustomerModel).where(and_(*conditions)).order_by(CustomerModel.created_at.desc()).limit(limit)`
   - Return `[r.to_dict() for r in result.scalars().all()]`
   - **Verify**: `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k customers` → all passed

4. **Implement `query_opportunities`**  
   - Same `limit` guard as `query_customers`
   - Conditions: `OpportunityModel.tenant_id == tenant_id`; if `keyword` present → ILIKE on `name`; if `keyword.isdigit()` → also `OpportunityModel.customer_id == int(keyword)`
   - Order by `created_at.desc()`, limit; return `[r.to_dict() for r in result.scalars().all()]`
   - **Verify**: `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k opportunities` → all passed

5. **Implement `query_tickets`**  
   - Same `limit` guard; conditions: `TicketModel.tenant_id == tenant_id`; if `status` present → `TicketModel.status == status`; if `keyword` present → ILIKE on `subject` and `description` (escaped)
   - Order by `created_at.desc()`, limit; return `[r.to_dict() for r in result.scalars().all()]`
   - **Verify**: `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k tickets` → all passed

6. **Implement `handle_message`**  
   - Guard empty text → `{"intent": "general", "query_results": None, "error": "empty message"}`
   - Call `classify_intent(text)`, then if/elif dispatching to appropriate helper:
     - `customer_lookup` → `query_customers(tenant_id, keyword=text)`
     - `sales_summary` → `query_opportunities(tenant_id, keyword=text)`
     - `ticket_query` → `query_tickets(tenant_id, keyword=text)`
     - `general` → no DB query
   - Catch `NotFoundException` / `ValidationException`, set `error` str
   - Return `{"intent": intent, "query_results": results, "error": error}`
   - **Verify**: `ruff check src/services/chat_service.py && mypy src/services/chat_service.py` → 0 errors each

7. **Create `tests/unit/test_chat_service.py`**   - Build a `mock_db_session` fixture: use `MockState` + `make_mock_session` with handlers for `customers`, `opportunities`, and `tickets` from `tests/unit/domain_handlers/`
   - Instantiate `ChatService(mock_db_session)` in each test
   - Test intent classification: one test per intent (regex hit), one for keyword fallback (longest-match), one for empty text (`ValidationException`)
   - Test each helper: success with keyword, success without keyword, `limit` validation error, tenant isolation
   - Test `handle_message`: one per intent dispatch, general fallback, empty text guard
   - **Verify**: `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → `≥ 8 passed`

## Test Plan

- **Unit tests in `tests/unit/`**:  
  Add `tests/unit/test_chat_service.py` covering:
  - `classify_intent`: customer_lookup (regex), ticket_query (regex), sales_summary (regex), general (no match), keyword longest-match tie-break, empty text raises `ValidationException`
  - `query_customers`: returns list[dict], ILIKE keyword match, filters by `tenant_id`, limit validation error
  - `query_opportunities`: returns list[dict], ILIKE on name, numeric keyword matches `customer_id`, limit validation error
  - `query_tickets`: returns list[dict], status filter, ILIKE on subject/description, tenant isolation, limit validation error
  - `handle_message`: dispatches to correct helper per intent, returns structured dict, catches and surfaces exceptions

- **Integration tests in `tests/integration/`**: none required per dev-plan scope

- **Dev-plan verification**: the dev-plan specifies no formal §6 verification script; manual checks per step are:
  - `ruff check src/services/chat_service.py` → 0 errors
  - `mypy src/services/chat_service.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → `≥ 8 passed`
  - `PYTHONPATH=src python -c "from services.chat_service import ChatService; print('import ok')"` → `import ok`

## Acceptance Criteria

- `ChatService.__init__` accepts a single required `AsyncSession` argument with no default
- `classify_intent` returns `"customer_lookup"` for messages containing `customer`/`customers` (not `ticket`), returns `"ticket_query"` for `ticket`/`support`/`issue`/`bug`, returns `"sales_summary"` for `deal`/`opportunity`/`forecast`/`revenue`/`pipeline`, returns `"general"` when no pattern matches
- `classify_intent("")` and `classify_intent("   ")` raise `ValidationException`
- `query_customers(tenant_id, keyword=None, limit=10)` returns `list[dict]` with all items having `tenant_id == tenant_id` and name/email ILIKE-matched when keyword is provided
- `query_opportunities(tenant_id, keyword=None, limit=10)` returns `list[dict]` filtered by `tenant_id`
- `query_tickets(tenant_id, keyword=None, status=None, limit=10)` returns `list[dict]` filtered by `tenant_id` and optionally by `status`
- All three helpers raise `ValidationException` when `limit <= 0 or limit > 200`
- `handle_message(text, tenant_id)` returns `dict` with keys `intent`, `query_results`, `error`
- `ruff check src/services/chat_service.py` and `mypy src/services/chat_service.py` both pass with 0 errors
- `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` runs ≥ 8 passed tests
