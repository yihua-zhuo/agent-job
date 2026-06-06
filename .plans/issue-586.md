Now I have all the context needed to write the plan. Here's the implementation plan:

# Implementation Plan — Issue #586

## Goal
Add an optional `lead_tier` filter and `order_by_score` auto-rank to `GET /customers/`, plus a `POST /events/engagement` webhook that records engagement events and triggers score recalculation via `ScoreService.calculate_score`, closing the lead-scoring feedback loop.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0586-add-lead-tier-filter-and-auto-rank-to-customer-list-endpoint.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0586-add-lead-tier-filter-and-auto-rank-to-customer-list-endpoint.md`

## Affected Files
- `src/api/routers/customers.py` — add `lead_tier` and `order_by_score` query params to `list_customers`; thread them to `CustomerService.list_customers`
- `src/services/customer_service.py` — extend `list_customers` signature with `lead_tier` and `order_by_score`; validate `lead_tier` against allowed set; pass through to `CustomerRepository.list_customers`
- `src/db/repositories/customer.py` — extend `list_customers` signature with `lead_tier` and `order_by_score`; add `CustomerModel.tier` equality filter and conditional `ORDER BY score DESC` (with `COALESCE(score, 0)` to handle NULL)
- `src/db/models/engagement.py` — new file; define `EngagementEventModel` (id, tenant_id, customer_id, event_type, event_metadata JSONB, created_at)
- `src/services/event_service.py` — new file; define `EventService` with `record_engagement_event(tenant_id, customer_id, event_type, metadata) -> EngagementEventModel`
- `src/api/routers/events.py` — new file; `APIRouter(prefix="/api/v1/events", tags=["events"])` with `POST /engagement` endpoint that calls `EventService.record_engagement_event` then `ScoreService.calculate_score`, returns `{"success": True, "data": {"customer_id": N, "score": M, "tier": "A"}}`
- `alembic/versions/<id>_add_engagement_events.py` — new migration; `CREATE TABLE engagement_events` with `tenant_id` index and `event_metadata` JSONB; manually verify `sa.JSONB()` and `sa.DateTime(timezone=True)`
- `tests/unit/test_customer_service.py` — add 4 new cases under `TestListCustomers`: hot filter, warm filter, cold filter, `order_by_score` parameter pass-through; plus 1 validation-error case for invalid tier value
- `tests/unit/test_events_webhook.py` — new file; unit tests for the events router: valid engagement POST returns 200 with score; invalid event_type returns 422; mock `ScoreService.calculate_score` assertion
- `tests/integration/test_engagement_webhook_integration.py` — new file; integration tests: POST engagement event → customer score/tier updated in DB; multi-tenant isolation; `order_by_score` returns highest-scoring customers first; `lead_tier` filter returns only matching tier

## Implementation Steps

1. **Extend `CustomerRepository.list_customers`** in `src/db/repositories/customer.py` (L38-64): add `lead_tier: str | None = None` and `order_by_score: bool = False` parameters; in the conditions list, add `CustomerModel.tier == lead_tier` when `lead_tier` is not None; for ordering, use `func.coalesce(CustomerModel.score, 0).desc()` when `order_by_score` is True, otherwise retain the existing `CustomerModel.created_at.desc()`.

2. **Extend `CustomerService.list_customers`** in `src/services/customer_service.py` (L48-63): add the same two parameters; validate `lead_tier` against the set `{"hot", "warm", "cold"}` and raise `ValidationException` for unknown values; forward both parameters to `self.repository.list_customers`.

3. **Update `GET /customers/` in `src/api/routers/customers.py`** (L213-244): add `lead_tier: str | None = Query(None, description="Filter by lead tier: hot, warm, cold")` and `order_by_score: bool = Query(False, description="Auto-rank by score descending")` parameters; pass both to `service.list_customers`. No changes to the enrichment enrichment loop or response envelope.

4. **Create `EngagementEventModel`** in `src/db/models/engagement.py`: columns `id` (Integer, PK), `tenant_id` (Integer, nullable=False, index=True), `customer_id` (Integer, nullable=False, index=True), `event_type` (String(50), nullable=False), `event_metadata` (JSON, nullable=True, default=dict), `created_at` (DateTime(timezone=True), server_default=func.now()). The model will be auto-discovered by `src/db/models/__init__.py` via `pkgutil.iter_modules` — no manual import needed there.

5. **Generate and fix Alembic migration**: run `alembic revision --autogenerate -m "add engagement_events table"` against the `alembic_dev` DB; manually correct `sa.JSON()` → `sa.JSONB()` on the `event_metadata` column; verify `sa.DateTime(timezone=True)` on `created_at`; run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` three-cycle; run a second `autogenerate` to confirm empty drift, then delete the drift-check file.

6. **Create `EventService`** in `src/services/event_service.py`: `__init__(self, session: AsyncSession)` with no default; `record_engagement_event(tenant_id, customer_id, event_type, metadata=None) -> EngagementEventModel` that constructs an `EngagementEventModel` instance, adds it, commits, refreshes, and returns. Validate `event_type` is in `{"email_open", "website_visit"}` and raise `ValidationException` otherwise.

7. **Create `POST /engagement` router** in `src/api/routers/events.py`: define `router = APIRouter(prefix="/api/v1/events", tags=["events"])` (auto-discovered by `iter_routers` — no `main.py` change needed). Define a Pydantic `EngagementEventRequest(BaseModel)` with `customer_id: int` (gt=0), `event_type: str` (pattern=`^(email_open|website_visit)$`), `metadata: dict | None = None`. The endpoint handler instantiates `EventService(session)` and `ScoreService(session)`, calls `record_engagement_event` then `calculate_score`, and returns `{"success": True, "data": {"customer_id": ..., "score": result.score, "tier": result.tier_label}}`. Auth via `Depends(require_auth)`.

8. **Add unit tests for `list_customers` parameter pass-through** in `tests/unit/test_customer_service.py`: a new `TestListCustomers` class with 4 cases — `test_list_customers_passes_lead_tier_hot` verifies `repo.list_customers` receives `lead_tier="hot"`; `test_list_customers_passes_lead_tier_warm`; `test_list_customers_passes_lead_tier_cold`; `test_list_customers_passes_order_by_score_true` verifies `order_by_score=True` is forwarded. Plus `test_list_customers_invalid_tier_raises_validation` which calls `service.list_customers(lead_tier="invalid")` and asserts `ValidationException`.

9. **Create unit tests for the engagement webhook** in `tests/unit/test_events_webhook.py`: use a mock `AsyncSession` with patched `EventService.record_engagement_event` and `ScoreService.calculate_score`; test that a valid POST returns the expected envelope; test that an invalid `event_type` returns 422 (Pydantic validation); assert `ScoreService.calculate_score` is awaited exactly once after the event is recorded.

10. **Create integration tests** in `tests/integration/test_engagement_webhook_integration.py`: seed a customer in a tenant, POST to `/api/v1/events/engagement` with `event_type="email_open"`, then query the customer row and assert `score` and `tier` are updated. Add a cross-tenant test: POST with `tenant_id=A` customer, query from `tenant_id=B` → should not see the event. Add a `lead_tier` filter test: seed two customers with different tier values, GET `/api/v1/customers/?lead_tier=hot` returns only the hot one. Add an `order_by_score` test: seed three customers with scores 10/50/90, GET `/api/v1/customers/?order_by_score=true` returns them in descending order.

11. **Run the full verification pipeline**: `ruff check src/ && ruff format --check src/` must exit 0; `PYTHONPATH=src pytest tests/unit/ -v` must pass; `PYTHONPATH=src pytest tests/integration/test_engagement_webhook_integration.py -v` must pass; `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` must complete without error.

## Test Plan
- Unit tests in `tests/unit/`: 
  - `test_customer_service.py` — add `TestListCustomers` class (4 pass-through cases + 1 validation case)
  - `test_events_webhook.py` — new file; mock-based tests for the `/engagement` endpoint covering valid POST, invalid event_type, and `ScoreService` invocation assertion
- Integration tests in `tests/integration/`:
  - `test_engagement_webhook_integration.py` — new file; full-DB tests for webhook trigger → score update, cross-tenant isolation, `lead_tier` filter accuracy, and `order_by_score` sort order
- Dev-plan verification:
  - §6 acceptance #1: `ruff check src/api/routers/customers.py src/api/routers/events.py src/services/customer_service.py src/services/event_service.py` → 0 errors
  - §6 acceptance #2: `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 4+ new cases passed
  - §6 acceptance #3: `PYTHONPATH=src pytest tests/unit/test_events_webhook.py -v` → all passed
  - §6 acceptance #4: `PYTHONPATH=src pytest tests/integration/test_engagement_webhook_integration.py -v` → all passed
  - §6 acceptance #5: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0 (covers Step 5 migration)
  - §6 E2E webhook: `curl -X POST /api/v1/events/engagement` with valid body → returns `{"success": true, "data": {"customer_id": N, "score": M, "tier": "..."}}`
  - §6 E2E list: `curl /api/v1/customers/?lead_tier=hot&order_by_score=true` → returns filtered, score-sorted list

## Acceptance Criteria
- `GET /api/v1/customers/?lead_tier=hot` (and `warm`, `cold`) returns only customers whose `tier` column matches; invalid tier values produce a 422 with `ValidationException`
- `GET /api/v1/customers/?order_by_score=true` returns customers sorted by `score DESC` (with NULLs treated as 0 via `COALESCE`)
- Both query parameters are optional and independent — omitting both preserves the existing `ORDER BY created_at DESC` behavior with no regression
- `POST /api/v1/events/engagement` with a valid body (authenticated) records an `EngagementEventModel` row and invokes `ScoreService.calculate_score` exactly once, returning the recalculated `score` and `tier` in the response
- The engagement event row is persisted with the correct `tenant_id`, `customer_id`, `event_type`, and `event_metadata`
- Cross-tenant isolation holds: a webhook POST for `tenant_id=A` is not visible or actionable from `tenant_id=B`
- All unit and integration tests pass; `ruff check` and `ruff format --check` are clean; migration applies and reverts cleanly in a three-cycle

## Risks / Open Questions
- **Tier value mapping**: The dev-plan body says `lead_tier` accepts `hot/warm/cold`, but the existing `CustomerModel.tier` column stores the `ScoreTier` enum values (`A`/`B`/`C`/`D`). The plan adds a `{"hot", "warm", "cold"}` validation set in the service layer, but the actual SQL filter operates on the stored letter tier. If callers expect hot/warm/cold to map to A/B/C, the mapping must be defined at the service or router boundary — not in the SQL query. This decision should be confirmed with the issue owner before implementation, as it may require updating the filter to translate input values to the stored enum.
- **Webhook auth model**: The dev-plan Step 3 uses `Depends(require_auth)`, which expects a user JWT. External systems (email trackers, website analytics) typically authenticate via a shared secret or API key, not user credentials. The plan follows the dev-plan's auth choice, but a production webhook would more likely use a header-based secret check. This should be confirmed with the issue owner if the webhook is intended for external system integration.
- **ScoreService persistence**: `ScoreService.calculate_score` (in `src/services/score_service.py`) is currently read-only — it computes a `ScoreResult` from the persisted `score_factors` JSON column but does not write the computed `score`/`tier` back to `CustomerModel`. The webhook calls `calculate_score` and then must persist the result. The plan assumes the webhook handler (or a follow-up) updates `customer.score` and `customer.tier` after calling `calculate_score`; if `ScoreService` is extended to persist as part of #585, this becomes simpler. This should be verified against the #585 implementation before starting work.
