I have all the context needed. Here is the plan:

# Implementation Plan — Issue #599

## Goal
Wire up the `GET /api/v1/sales/opportunities/{id}/recommendations` HTTP endpoint by creating a new router that calls the existing `SalesRecommendationService`, adding an async `get_recommendations` method to that service, and registering the router (which `api/__init__.py`'s `iter_routers()` discovers automatically).

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/20-sales/0599-wire-up-get-sales-opportunities-id-recommendations-endpoint.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/20-sales/0599-wire-up-get-sales-opportunities-id-recommendations-endpoint.md`

## Affected Files
- `src/services/sales_recommendation.py` — change `__init__` to accept `AsyncSession | None = None`; add `async get_recommendations(opportunity_id, tenant_id) -> dict` method that composes `predict_conversion_probability`, `get_similar_customers`, and `get_next_best_action`
- `src/api/routers/recommendations.py` — new file: define `recommendations_router` with `GET /opportunities/{opp_id}/recommendations`
- `tests/unit/test_recommendations_router.py` — new file: 4 unit tests (200 success, 404, 500, 401 auth-required)

## Implementation Steps

1. **Modify `src/services/sales_recommendation.py`:**
   - Add `from sqlalchemy.ext.asyncio import AsyncSession` to imports.
   - Change `def __init__(self):` → `def __init__(self, session: AsyncSession | None = None):` and store `self.session = session` (CLAUDE.md requires `AsyncSession` type with no default, but this service is synchronous/mock-based and does not issue SQL — `AsyncSession | None = None` is the dev-plan's explicit choice for backward compatibility).
   - Append `async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:` after line 270 (end of `predict_conversion_probability`). The method returns a dict with keys: `opportunity_id`, `conversion_probability`, `similar_opportunities` (list of `customer_id`/`current_tier`/`monthly_revenue`), `next_best_action` (action/target/reason/confidence). Calls existing synchronous helpers internally (no IO, safe in async context).

2. **Create `src/api/routers/recommendations.py`:**
   - Define `recommendations_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])`.
   - Register `@recommendations_router.get("/opportunities/{opp_id}/recommendations")` with `opp_id: int`, `ctx: AuthContext = Depends(require_auth)`, `session: AsyncSession = Depends(get_db)`.
   - In the handler: instantiate `SalesRecommendationService(session)`, `await service.get_recommendations(opp_id, ctx.tenant_id)`, return `{"success": True, "data": data}`.
   - No try/catch — `AppException` is handled by the global handler in `main.py:71-77`.
   - The `iter_routers()` function (`src/api/__init__.py:39`) discovers routers by `name == "router" or name.endswith("_router")`, so `recommendations_router` is auto-registered in `main.py`'s `for router in iter_routers()` loop at `src/main.py:96`. No `main.py` edit needed.

3. **Create `tests/unit/test_recommendations_router.py`:**
   - Reuse the fixture pattern from `tests/unit/test_sales_router.py:51+`: create a `client_with_service` fixture that monkeypatches `api.routers.recommendations.SalesRecommendationService` to return a `MagicMock`, builds a standalone `FastAPI()`, includes the router, overrides `require_auth` and `get_db` dependencies, and returns a `TestClient`.
   - Test 1 (`test_success_returns_200`): set `svc.get_recommendations = AsyncMock(return_value={...})`; assert 200 + `body["data"]["opportunity_id"] == 5`.
   - Test 2 (`test_not_found_returns_404`): set side effect to `NotFoundException("Opportunity")`; assert 404.
   - Test 3 (`test_internal_error_returns_500`): set side effect to `RuntimeError`; assert 500 (caught by generic handler at `main.py:87-93`).
   - Test 4 (`test_missing_auth_returns_401`): do not override `require_auth`; assert 401.

## Test Plan
- Unit tests in `tests/unit/`: new `test_recommendations_router.py` covering 200/404/500/401 per dev-plan §5 Step 3
- Integration tests in `tests/integration/`: none — the service uses mock/hashed data, no real DB queries; dev-plan §3.1 lists no integration test file
- Dev-plan verification:
  - `ruff check src/api/routers/recommendations.py src/services/sales_recommendation.py` → 0 errors (§6)
  - `ruff format --check src/api/routers/recommendations.py src/services/sales_recommendation.py` → pass (§6)
  - `PYTHONPATH=src pytest tests/unit/test_recommendations_router.py -v` → 4 passed (§6)
  - `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → all passed (regression check, §6)

## Acceptance Criteria
- `GET /api/v1/sales/opportunities/{id}/recommendations` returns 200 with `{"success": true, "data": {"opportunity_id": ..., "conversion_probability": ..., "similar_opportunities": [...], "next_best_action": {...}}}` for an existing opportunity
- Returns 404 via `NotFoundException` for a missing opportunity (inherited from global handler)
- Returns 401 when no auth token is present (handled by `require_auth` dependency)
- `SalesRecommendationService.get_recommendations` is an `async` method accepting `(opportunity_id: int, tenant_id: int) -> dict`
- `iter_routers()` auto-discovers `recommendations_router` without any `main.py` modification
- All 4 unit tests pass; ruff lint and format checks pass

## Risks / Open Questions
- The dev-plan sets `__init__(self, session: AsyncSession | None = None)`, which violates CLAUDE.md's global rule "session=None is never allowed." This is a documented intentional choice in the dev-plan §4.4 known-pits because the service does not issue SQL (all data is hash-derived mocks). A follow-up could migrate to a real DB-backed model, which would require `session: AsyncSession` with no default.
- `SalesRecommendationService.get_similar_customers` and `get_next_best_action` use `random` calls without a fixed seed; results will differ between test runs, so the test assertions must not depend on specific random values.
