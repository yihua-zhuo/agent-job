Now I have a thorough understanding of the codebase. Here is the plan:

---

# Implementation Plan — Issue #512

## Goal

Wire third-party enrichment data into the `CustomerService` create/update flow by upserting `CustomerEnrichmentModel` records whenever a customer is created or updated with enrichment payload. Add `enrichment_status` and `last_enriched_at` derived fields to the customer API response schema. Add a `POST /api/v1/enrichment/refresh/{customer_id}` endpoint that re-calls the enrichment provider and updates the record using an upsert pattern. Write unit tests for the upsert logic and refresh endpoint.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0512-wire-enrichment-data-into-customer-create-update-and-add-sta.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/10-customers/0512-wire-enrichment-data-into-customer-create-update-and-add-sta.md`

## Affected Files

- `src/services/customer_service.py` — add `upsert_enrichment()` helper and call it from `create_customer` / `update_customer` when `enrichment_data` is present in the payload
- `src/models/enrichment.py` — add `EnrichmentRefreshRequest` Pydantic schema and `enrichment_status` / `last_enriched_at` fields
- `src/api/routers/enrichment.py` — add `POST /api/v1/enrichment/refresh/{customer_id}` endpoint
- `src/db/models/customer_enrichment.py` — already exists and is complete; no changes needed
- `src/db/models/customer.py` — no schema changes needed; status is derived in the router from the joined enrichment record
- `src/api/routers/customers.py` — enrich `GET /` and `GET /{id}` responses with `enrichment_status` and `last_enriched_at` from the joined `CustomerEnrichmentModel` record
- `tests/unit/test_customer_service.py` — add tests for enrichment upsert on create and update
- `tests/unit/test_enrichment_router.py` — add tests for the `POST /api/v1/enrichment/refresh/{customer_id}` endpoint
- `alembic/versions/` — no new migration; `CustomerEnrichmentModel` is already covered by `f18b406b982a_create_customer_enrichments.py`, and the status fields are derived, not stored columns

## Implementation Steps

**Step 1: Add `upsert_enrichment` to `CustomerService`**

In `src/services/customer_service.py`, import `CustomerEnrichmentModel` and add a private `async def _upsert_enrichment(...)` helper that uses `INSERT … ON CONFLICT (tenant_id, customer_id) DO UPDATE SET raw_data_json=…, enriched_at=…, provider=…, updated_at=now()` via SQLAlchemy's `insert().on_conflict_do_update()`. Call this helper at the end of both `create_customer` (after flush) and `update_customer` (after flush) when the incoming `data` dict contains an `enrichment_data` key with a non-None value. The upsert is tenant-scoped via `(tenant_id, customer_id)` uniqueness constraint already defined on the model.

**Step 2: Add derived enrichment fields to customer Pydantic schema**

In `src/models/enrichment.py`, add a `class EnrichmentStatusOut(BaseModel)` with `enrichment_status: Literal["none", "enriched", "stale"]` and `last_enriched_at: datetime | None`. Add a `class EnrichmentRefreshRequest(BaseModel)` with optional `domain: str | None` and `company_name: str | None`.

**Step 3: Add `POST /api/v1/enrichment/refresh/{customer_id}` endpoint**

In `src/api/routers/enrichment.py`, add a `refresh_enrichment` endpoint that accepts `customer_id` as a path param, optionally accepts an `EnrichmentRefreshRequest` body, calls `EnrichmentService.refresh(...)` (new method to implement), and returns the refreshed `CustomerEnrichmentModel`. The endpoint is tenant-scoped via `require_auth`.

**Step 4: Add `refresh` method to `EnrichmentService`**

In `src/services/enrichment_service.py`, add `async def refresh(self, customer_id: int, tenant_id: int, domain: str | None, company_name: str | None) -> dict[str, Any]`. This method verifies customer ownership, calls `self._lookup_clearbit(...)`, then upserts the `CustomerEnrichmentModel` record using the same `insert().on_conflict_do_update()` pattern. Returns the normalised dict.

**Step 5: Add enrichment status to customer GET responses**

In `src/api/routers/customers.py`, in both `get_customer` and `list_customers`, after fetching the `CustomerModel`, execute a second query to find the most recent `CustomerEnrichmentModel` for that `customer_id` and compute `enrichment_status`:
- `"none"` if no enrichment record exists
- `"stale"` if `next_refresh_at` is in the past
- `"enriched"` otherwise

Add `last_enriched_at` (from `enriched_at`) to the response dict alongside the existing customer fields. No change to the ORM model is needed — this is a router-layer join.

**Step 6: Add unit tests for enrichment upsert in `test_customer_service.py`**

Add a `TestEnrichmentUpsert` class with:
- `test_create_customer_with_enrichment_data_calls_upsert` — patch `_upsert_enrichment`, call `create_customer` with `{"name": "X", "enrichment_data": {"raw": "payload"}}`, assert the patch was called with the customer id and payload.
- `test_update_customer_with_enrichment_data_calls_upsert` — mock `get_customer` to return a customer, patch `_upsert_enrichment`, call `update_customer` with `{"enrichment_data": {"raw": "updated"}}`, assert upsert called.
- `test_create_customer_without_enrichment_data_skips_upsert` — assert `_upsert_enrichment` is NOT called when no `enrichment_data` key is present.

**Step 7: Add unit tests for refresh endpoint in `test_enrichment_router.py`**

Add a `TestRefreshEndpoint` class with:
- `test_refresh_returns_enriched_data` — mock `EnrichmentService.refresh`, assert 200 and `success: True`.
- `test_refresh_passes_correct_args` — assert `svc.refresh` was called with `customer_id`, `tenant_id`, domain/company_name from request body.
- `test_refresh_customer_not_found_returns_404` — mock service to raise `NotFoundException`, assert 404.

## Test Plan

- Unit tests in `tests/unit/test_customer_service.py`: add `TestEnrichmentUpsert` covering create/update with and without enrichment payload (Step 6).
- Unit tests in `tests/unit/test_enrichment_router.py`: add `TestRefreshEndpoint` covering success, arg-passing, and 404 cases (Step 7).
- Integration tests: not required by the issue; enrichment external call is mocked in unit tests and verified manually via `POST /api/v1/enrichment/refresh/{id}` in staging.
- Dev-plan verification: `PYTHONPATH=src ruff check src/services/customer_service.py src/api/routers/enrichment.py` must exit 0; `PYTHONPATH=src pytest tests/unit/test_customer_service.py tests/unit/test_enrichment_router.py -v` must pass all new and existing tests.

## Acceptance Criteria

- `POST /api/v1/customers` with `{"name": "Acme", "enrichment_data": {"domain": "acme.com"}}` persists a `CustomerEnrichmentModel` row for that customer.
- `PUT /api/v1/customers/{id}` with `{"enrichment_data": {"company_name": "Acme Corp"}}` upserts (updates) the existing `CustomerEnrichmentModel` row instead of creating a duplicate.
- `GET /api/v1/customers/{id}` response includes `enrichment_status` (`"none" | "enriched" | "stale"`) and `last_enriched_at` (ISO datetime or null).
- `POST /api/v1/enrichment/refresh/{customer_id}` returns 200 and the normalised enrichment data; re-running it updates the existing record's `enriched_at` timestamp.
- Unit test suite: `PYTHONPATH=src pytest tests/unit/test_customer_service.py tests/unit/test_enrichment_router.py -v` → all pass with no new coverage gaps.
- Lint: `ruff check src/services/customer_service.py src/api/routers/enrichment.py` → 0 errors.
