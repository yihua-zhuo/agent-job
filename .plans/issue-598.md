Now I have all the context needed. Let me look at the `opportunity_handler` in `sales.py` domain handler to confirm it provides a row with `scalar_one_or_none` support (it returns a `MockResult` with one `MockRow`, so `scalar_one_or_none` returns the first row object).

The dev-plan's `opportunity_handler` returns a `MockResult([MockRow({...})])` when `"from opportunities"` is queried. Since `MockResult.scalar_one_or_none()` returns `self._rows[0] if self._rows else None`, the row is a `MockRow` (a dict-like mapping), not an `OpportunityModel` instance. The service code calls `opp.customer_id`, which will work via `MockRow.__getattr__`.

Now I have enough to write the plan.

# Implementation Plan — Issue #598

## Goal

Add `RecommendationService` in `src/services/recommendation_service.py` that wraps `SalesRecommendationService` with a module-level in-memory TTL cache (3600 s). Expose `get_recommendations(opportunity_id, tenant_id)` (cache hit returns cached dict; miss/stale recomputes and caches) and `invalidate_cache(opportunity_id, tenant_id)` (static, removes cache entry on stage change). Raises `NotFoundException("Opportunity")` if the opportunity row does not exist for the given tenant.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/20-sales/0598-add-recommendation-service-with-caching.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/20-sales/0598-add-recommendation-service-with-caching.md`

## Affected Files

- `src/services/recommendation_service.py` — **new file**: `RecommendationService(session)` with module-level `_cache: dict[str, tuple[float, dict]]`, TTL constant `3600.0`, `get_recommendations()`, `invalidate_cache()` (static), plus helper `_cache_key(opportunity_id, tenant_id)`
- `tests/unit/test_recommendation_service.py` — **new file**: 5 unit tests (cache miss populates, cache hit returns same data, stale cache is bypassed, invalidate removes entry, not-found raises `NotFoundException`)

No other files are modified. `src/services/__init__.py` does not exist, so no module export update is needed — consumers import directly: `from services.recommendation_service import RecommendationService`. The dev-plan's §3.2 "TBD" export step collapses to a no-op.

## Implementation Steps

1. **Create `src/services/recommendation_service.py`** following the dev-plan §5 Step 1 code block exactly:
   - Module-level `_CACHE_TTL = 3600.0` and `_cache: dict[str, tuple[float, dict]] = {}` (singleton, module-level so it survives across per-request `RecommendationService` instances)
   - Helper `_cache_key(opportunity_id: int, tenant_id: int) -> str` returns `f"{opportunity_id}:{tenant_id}"`
   - `class RecommendationService` with `__slots__ = ("session", "_sales_svc")`
   - `__init__(self, session: AsyncSession)` — stores session, instantiates `self._sales_svc = SalesRecommendationService()` (its `__init__` takes no args, per `src/services/sales_recommendation.py:62`)
   - `async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict`:
     - Build key, check cache; if present and `now - ts < _CACHE_TTL`, return the cached dict immediately
     - Otherwise `select(OpportunityModel).where(id == opportunity_id, tenant_id == tenant_id)` and `scalar_one_or_none()`; if `None` → `raise NotFoundException("Opportunity")`
     - Build result dict with keys: `opportunity_id`, `conversion_probability` (from `self._sales_svc.predict_conversion_probability(opportunity_id)`), `next_action` (from `self._sales_svc.get_next_best_action(tenant_id, opp.customer_id)`), `similar_deals` (`[]`, to be populated by follow-up issue #667)
     - Write `_cache[key] = (now, data)` and return
   - `@staticmethod def invalidate_cache(opportunity_id: int, tenant_id: int) -> None` — `_cache.pop(_cache_key(opportunity_id, tenant_id), None)` (no raise on missing key)
   - Import `from services.sales_recommendation import SalesRecommendationService` (confirmed: `src/services/sales_recommendation.py:43`)
   - Import `from db.models.opportunity import OpportunityModel` (confirmed: `src/db/models/opportunity.py:12`)
   - Import `from pkg.errors.app_exceptions import NotFoundException` (confirmed: `src/pkg/errors/app_exceptions.py:21` — `NotFoundException(resource: str)` sets 404 + `"<resource> not found"`)
   - Import `from sqlalchemy import select` and `from sqlalchemy.ext.asyncio import AsyncSession`

2. **Create `tests/unit/test_recommendation_service.py`** with its own `mock_db_session` fixture per CLAUDE.md §Unit Test SQL Mocks:
   - Fixture: `MockState()` + `make_mock_session([opportunity_handler, make_customer_handler(state)])` — `opportunity_handler` from `tests/unit/domain_handlers/sales.py:21` handles `"from opportunities"` queries and returns a `MockResult` with one `MockRow`; `scalar_one_or_none()` on that result returns the `MockRow`, which exposes `customer_id` via `MockRow.__getattr__` (conftest.py:82)
   - Fixture: `svc` clears `_cache` and patches `time.time` to a fixed value `1000.0` via `monkeypatch`
   - **test_cache_miss_populates_cache** — call `get_recommendations(1, tenant_id=1)`, assert `_cache_key(1, 1) in _cache`, assert the cached tuple's data equals the returned dict
   - **test_cache_hit_returns_cached_data** — call twice with same args, assert both returns are equal (cache short-circuits before DB hit)
   - **test_stale_cache_is_bypassed** — call once, advance `time.time` to `1000.0 + _CACHE_TTL + 1`, call again, assert result is fresh (entry timestamp in `_cache` is updated, proves recompute happened)
   - **test_invalidate_removes_cache_entry** — call once (populates cache), call `RecommendationService.invalidate_cache(1, 1)`, assert key absent
   - **test_not_found_raises** — replace `mock_db_session.execute` with `AsyncMock(return_value=MockResult([]))` (empty rows → `scalar_one_or_none()` returns `None`), call with opportunity_id=9999, assert `pytest.raises(NotFoundException)`
   - **test_tenant_isolation_in_cache_key** — call `get_recommendations(1, tenant_id=1)` and `get_recommendations(1, tenant_id=2)`, assert two distinct cache entries exist (confirms key is `(opportunity_id, tenant_id)` composite, not opportunity alone)

3. **Verify lint** — run `PYTHONPATH=src ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → expect 0 errors. Also run `PYTHONPATH=src ruff format --check` on both files.

4. **Run unit tests** — `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → expect 6 passed (the 5 dev-plan cases + tenant isolation guard).

5. **Run regression** — `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → expect all passed (per dev-plan §1.4 KPI).

## Test Plan

- Unit tests in `tests/unit/`: create `test_recommendation_service.py` with 6 tests covering cache miss, cache hit, stale bypass, invalidate, not-found, and tenant-key isolation. Uses `make_mock_session` + `opportunity_handler` (from `tests/unit/domain_handlers/sales.py`) + `make_customer_handler` (from `tests/unit/domain_handlers/customers.py`) with a shared `MockState`.
- Integration tests in `tests/integration/`: none — the dev-plan scope is unit-only; the cache layer is a pure in-memory abstraction with no DB writes of its own, and the underlying `SalesRecommendationService` methods (`predict_conversion_probability`, `get_next_best_action`) are pure functions of `opportunity_id`/`tenant_id`/`customer_id` (no DB I/O), so integration coverage of the cache adds no value.
- Dev-plan verification (target board §6):
  - `PYTHONPATH=src ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors
  - `PYTHONPATH=src ruff format --check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 6 passed
  - `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → all passed (regression)
  - `PYTHONPATH=src mypy src/services/recommendation_service.py` → 0 errors
  - Alembic upgrade/downgrade loop: **not applicable** — this issue introduces no new ORM model or migration. The `recommendations` and `risk_signals` tables were created by migration `3c19d099a7a9` (the #597 deliverable, already applied). The dev-plan §6 line "`alembic upgrade head && alembic downgrade -1` → exit 0（如 #597 migration 存在）" is conditional on #597 and can be skipped if #597 is already merged.

## Acceptance Criteria

- `RecommendationService(session: AsyncSession)` constructs without error; `session` is typed as `AsyncSession` with no default (per CLAUDE.md §Service Pattern).
- First call to `get_recommendations(opportunity_id, tenant_id)` with a real opportunity populates `_cache` and returns a dict with keys `opportunity_id`, `conversion_probability`, `next_action`, `similar_deals`.
- Second call within 3600 s returns the identical cached dict without executing the opportunity `SELECT`.
- Second call after 3600 s executes the `SELECT` and refreshes the cache entry's timestamp.
- `get_recommendations` with an opportunity_id that does not exist for the given tenant raises `NotFoundException` (status 404, code `NOT_FOUND`).
- `RecommendationService.invalidate_cache(opportunity_id, tenant_id)` removes the entry; calling it on a non-existent key does not raise.
- Cache entries are keyed by `"<opportunity_id>:<tenant_id>"` — two different tenants querying the same opportunity_id produce two separate cache entries.
- `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 6 passed.
- `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → all passed (regression intact).
- `PYTHONPATH=src ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors.

## Risks / Open Questions

- **#597 merge ordering**: `RecommendationService` imports `OpportunityModel` (existed pre-#597) and the `recommendations`/`risk_signals` tables (from #597 migration `3c19d099a7a9`). The dev-plan flags this as a low-probability risk; if #597 is unmerged, the service itself still imports fine (it doesn't use `RecommendationModel`/`RiskSignalModel`), but the dev-plan §6 alembic loop can only be exercised post-#597.
- **Module-level cache + test ordering**: The singleton `_cache` persists across tests in the same process. The dev-plan §4.4 mitigates this via `_cache.clear()` in fixtures; the test file must do this in every fixture that writes to the cache. Failure to clear in a test that reads from the cache will produce a false cache hit — the test file should call `_cache.clear()` at the top of both the `svc` fixture and each test that needs a known state.
- **In-process cache in multi-worker deploy**: Identified in the dev-plan §7 risk table. Not a correctness issue; only a cache-hit-rate degradation. Out of scope for this issue (explicitly excluded by §1.3 — "不引入 Redis").
