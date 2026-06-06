I have all the information I need. Key findings:
- `ScoreService.calculate_score` returns a `tuple[int, str, list[str], list[str]]` (not `ScoreResponse` as the dev-plan assumed)
- `ScoreService.get_score` also returns a `tuple[int, str, list[str], list[str]]`
- Both methods raise `NotFoundException` when customer is not found
- The test file is `tests/unit/test_customers_router.py` (not `test_customers.py`)
- `NotFoundException` is at `src/pkg/errors/app_exceptions.py`

---

# Implementation Plan — Issue #584

## Goal
Wire `ScoreService` into the customers router by adding two authenticated REST endpoints — `POST /api/v1/customers/{customer_id}/score` (triggers score calculation) and `GET /api/v1/customers/{customer_id}/score` (returns current score or 404) — following the existing router pattern (AuthContext + `Depends(get_db)` + `{"success": True, "data": ...}` envelope).

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0584-wire-scoreservice-into-post-and-get-customers-id-score-route.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0584-wire-scoreservice-into-post-and-get-customers-id-score-route.md`

## Affected Files
- `src/api/routers/customers.py` — Add `ScoreService` import, `NotFoundException` import, and two new endpoint functions (`POST /{customer_id}/score`, `GET /{customer_id}/score`) at the end of the router definition
- `tests/unit/test_customers_router.py` — Add a new test class `TestScoreEndpoints` covering POST success, GET success, GET 404, and auth-required behavior

## Implementation Steps
1. **Add imports to `src/api/routers/customers.py`**: Add `from services.score_service import ScoreService` and `from pkg.errors.app_exceptions import NotFoundException` to the existing import block (lines 7–24). ScoreService is already defined in `src/services/score_service.py` and its methods (`calculate_score`, `get_score`) return `tuple[int, str, list[str], list[str]]` representing `(score, tier_value, top_factors, recommendations)`. The `GET` endpoint will need `NotFoundException` for 404 responses (the dev-plan assumes `get_score` returns `None` when no score exists, but the actual implementation raises `NotFoundException` internally — see note below).

2. **Add `POST /api/v1/customers/{customer_id}/score` endpoint**: Append a new route function at the end of `src/api/routers/customers.py` (after the last existing route, after line 544). The function should accept `customer_id: int` as a path param, inject `AuthContext` and `AsyncSession` via `Depends`, call `ScoreService(session).calculate_score(customer_id, tenant_id=ctx.tenant_id)`, and return the result wrapped in `{"success": True, "data": ...}`. The tuple return type must be converted to a dict before serialization (e.g. `{"score": r[0], "tier": r[1], "top_factors": r[2], "recommendations": r[3]}`). No `status_code=201` decorator argument is needed unless the dev-plan §3.3 implies it (the dev-plan example shows `status.HTTP_201_CREATED` but 200/200 is more conventional for a triggered computation — align with the codebase pattern of other POSTs in this file that omit explicit status).

3. **Add `GET /api/v1/customers/{customer_id}/score` endpoint**: Append a second route function. Call `ScoreService(session).get_score(customer_id, tenant_id=ctx.tenant_id)`. `ScoreService.get_score` raises `NotFoundException("Score")` when the customer has no score factors (empty `top_factors` and `recommendations`), and `NotFoundException("Customer")` when the customer row itself does not exist; the global exception handler converts both to 404. Otherwise the service returns the tuple and the router shapes it into the standard envelope.

4. **Add test class `TestScoreEndpoints` in `tests/unit/test_customers_router.py`**: After the last test class (after line 422), add four test methods:
   - `test_post_score_returns_data` — Mock `ScoreService.calculate_score` to return a `(85, "B", ["engagement_level"], ["Increase touchpoints..."])` tuple, POST to `/api/v1/customers/1/score`, assert 200 and response body contains the expected fields
   - `test_get_score_returns_data` — Mock `ScoreService.get_score` to return a tuple, GET `/api/v1/customers/1/score`, assert 200 and data structure
   - `test_get_score_returns_404_when_no_score` — Mock `ScoreService.get_score` to return a default/neutral tuple (or mock the session to return a customer with empty `score_factors`), GET `/api/v1/customers/9999/score`, assert 404
   - `test_score_endpoints_require_auth` — Remove the `require_auth` override from the test app, POST/GET to the score endpoints, assert 401

   Use the existing `client_with_service` fixture pattern, but the new test class needs its own fixture or monkeypatch override for `ScoreService` since the existing fixture patches `CustomerService` and `CustomerRepository`. Add a parallel fixture `client_with_score_service` that additionally patches `api.routers.customers.ScoreService` to return an `AsyncMock`.

5. **Run lint and test verification**:
   - `ruff check src/api/routers/customers.py tests/unit/test_customers_router.py` → 0 errors
   - `ruff format --check src/api/routers/customers.py tests/unit/test_customers_router.py` → exit 0
   - `PYTHONPATH=src pytest tests/unit/test_customers_router.py -v` → all passed including new score tests

## Test Plan
- **Unit tests in `tests/unit/`**: Modify `tests/unit/test_customers_router.py` — add `TestScoreEndpoints` class with ≥ 4 test methods covering: (1) POST returns 200 with score/tier/factors data, (2) GET returns 200 with existing score data, (3) GET returns 404 when customer has no score factors, (4) both endpoints return 401 without auth. The new class will need a dedicated fixture (or monkeypatch) to mock `ScoreService` in the router module namespace, following the same pattern as the existing `client_with_service` fixture.
- **Integration tests in `tests/integration/`**: None — the dev-plan §1.3 explicitly excludes DB/ORM changes and this issue only wires an already-tested service into the HTTP layer. Integration coverage is unnecessary since ScoreService itself is already integration-tested in #583.
- **Dev-plan verification**:
  - §1.4 KPI: `PYTHONPATH=src pytest tests/unit/test_customers_router.py -v` → all passed (including new score tests)
  - §1.4 KPI: `ruff check src/api/routers/customers.py` → 0 errors
  - §1.4 KPI: `ruff format --check src/api/routers/customers.py` → exit 0
  - §1.4 KPI: `PYTHONPATH=src python -c "from api.routers.customers import customers_router; print(len(customers_router.routes))"` → exit 0 (verifies imports resolve)
  - §6 acceptance: `ruff check src/api/routers/customers.py tests/unit/test_customers_router.py` → 0 errors
  - §6 acceptance: `ruff format --check src/api/routers/customers.py tests/unit/test_customers_router.py` → exit 0
  - §6 acceptance: no Alembic command — dev-plan §1.3 explicitly states no migration is involved in this issue ("不在 router 层引入新的数据库表或 ORM model")

## Acceptance Criteria
- `POST /api/v1/customers/{customer_id}/score` returns 200 with `{"success": true, "data": {"score": <int>, "tier": <str>, "top_factors": <list>, "recommendations": <list>}}` when authenticated
- `GET /api/v1/customers/{customer_id}/score` returns 200 with the same data structure when a score exists for the customer
- `GET /api/v1/customers/{customer_id}/score` returns 404 with `{"success": false, "message": "Score ..."}` when the customer has never been scored
- Both endpoints return 401 when no auth token is provided
- `ruff check` and `ruff format --check` pass with 0 errors on both modified files
- All existing tests in `tests/unit/test_customers_router.py` continue to pass

## Risks / Open Questions
- **Tuple vs Pydantic return type**: The dev-plan §2.1 states `ScoreService.calculate_score` returns `ScoreResponse` (a Pydantic model), but the actual implementation in `src/services/score_service.py` returns `tuple[int, str, list[str], list[str]]`. The router must convert the tuple to a dict manually. The plan above accounts for this discrepancy.
- **GET 404 semantics**: The dev-plan says `get_score` should return `None` if never scored, but the actual implementation always returns a tuple (defaulting to neutral score). The router needs to define "never scored" as a condition (e.g., empty `top_factors` or empty `score_factors` on the customer row) and raise `NotFoundException` accordingly. This requires checking the tuple's `top_factors` and `recommendations` lists for emptiness.
- **Route ordering**: FastAPI matches routes in declaration order. Since `/{customer_id}/score` is a sub-path of `/{customer_id}`, it must be declared after the base `GET /{customer_id}` and `DELETE /{customer_id}` routes to avoid parameter collision. The plan places new routes at the end of the file, which is correct.
