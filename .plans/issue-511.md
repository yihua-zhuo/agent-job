Now I have enough context to write the plan.

---

# Implementation Plan — Issue #511

## Goal
Build `EnrichmentService` in `src/services/enrichment_service.py` as the first provider-backed service in the enrichment subsystem, with `POST /api/v1/enrichment/lookup` in `src/api/routers/enrichment.py` as the sole public endpoint. The endpoint accepts a company domain or name, calls the Clearbit Company API (key driven by a config setting), normalizes the response into a company data dict, persists the raw payload to the `customer_enrichments` table already provisioned by issue #510, and returns the enriched fields.

## Source Contract
GitHub issue #511 body and repository files inspected during planning:
- `src/configs/settings.py` — config pattern (pydantic-settings `Field`, settings singleton)
- `src/services/ai_service.py` — service pattern (`AsyncSession` constructor arg, no default, raises `AppException`)
- `src/api/routers/ai.py` — router pattern (`_success()` wrapper, `Depends(get_db)`, `require_auth`)
- `src/db/models/customer_enrichment.py` — ORM model already created by issue #510 (FK to `customers.id`, `raw_data_json`, `provider`)
- `tests/unit/test_ai_service.py` — unit test style (mock `session.execute`, mock gateway, `MagicMock`/`AsyncMock`)
- `tests/unit/test_ai_router.py` — router test style (`FastAPI.TestClient`, monkeypatched `require_auth`/`get_db`)
- `src/db/connection.py` — `get_db` dependency## Affected Files
- `src/configs/settings.py` — Add `clearbit_api_key: str | None` field- `src/services/enrichment_service.py` — New file: `EnrichmentService` class with `lookup(domain, provider) -> dict`
- `src/api/routers/enrichment.py` — New file: `POST /api/v1/enrichment/lookup` endpoint
- `tests/unit/test_enrichment_service.py` — New file: unit tests for the service
- `tests/unit/test_enrichment_router.py` — New file: unit tests for the router endpoint

## Implementation Steps
1. **Add `clearbit_api_key` to settings**: In `src/configs/settings.py`, add `clearbit_api_key: str | None = Field(default=None)` alongside the other auth/API fields. No validation gate is needed (enrichment is optional functionality).
2. **Create `src/services/enrichment_service.py`**: Define `EnrichmentService(session: AsyncSession)` (no gateway/default). Implement `async def lookup(self, domain: str | None, company_name: str | None, *, tenant_id: int | None = None, customer_id: int | None = None) -> dict` that:
   - Normalises `domain` and `company_name` by stripping whitespace and treating blank strings as absent.
   - Requires exactly one of `domain`/`company_name` (raise `ValidationException` if both or neither given).
   - When `tenant_id` is provided, looks up the customer and raises `NotFoundException` if the `customer_id` does not belong to that tenant.
   - Dispatches to `_lookup_clearbit()` for `provider="clearbit"`.
   - Uses `httpx.AsyncClient` to `GET https://company.clearbit.com/v2/companies/find?name=<company_name>` or `?domain=<domain>` with `Authorization: Bearer <clearbit_api_key>` header.
   - On HTTP 404 raise `ValidationException("No company found for the given domain or name")`; on other non-2xx responses raise `ValidationException(f"Clearbit API error: {status_code}")`.
   - Normalize the Clearbit JSON into a flat `dict` with keys such as `name`, `domain`, `legal_name`, `category`, `geo`, `metrics`, `linkedin`, `logo` (include only present keys).
   - Insert a `CustomerEnrichmentModel` row with `customer_id`, `provider="clearbit"`, `raw_data_json=clearbit_response`, `enriched_at=now`.
   - Return the normalized dict.
   - Raise `ValidationException` for unknown `provider`.
3. **Create `src/api/routers/enrichment.py`**: Define an `enrichment_router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])`. Add `POST /lookup` with body `EnrichmentLookupRequest(domain: str | None = None, company_name: str | None = None)` (Pydantic model in `models/enrichment.py`). The endpoint calls `EnrichmentService(session).lookup(...)`, wraps in `_success()`, and returns the envelope dict.
4. **Validate dependency order**: The service inserts a `CustomerEnrichmentModel` row — verify `CustomerEnrichmentModel` is importable and its table has been migrated via the existing issue #510 migration (`create_customer_enrichments`). No new migration required.

## Test Plan
- Unit tests in `tests/unit/`: `test_enrichment_service.py` — mock `httpx.AsyncClient` via `AsyncMock`/`MagicMock` patched at the `httpx.AsyncClient` class level; test `lookup` with domain, with company_name, with neither (raises `ValidationException`), with both (raises `ValidationException`), HTTP 404 (raises `ValidationException`), HTTP 500 (raises `ValidationException`), provider=clearbit success (returns normalized dict). Also test that `CustomerEnrichmentModel` is added to the session.
- Unit tests in `tests/unit/`: `test_enrichment_router.py` — create a `TestClient` via `FastAPI.TestClient`, monkeypatch `require_auth` (returns `AuthContext`) and `get_db` (returns `MagicMock`); mock `EnrichmentService.lookup` with `AsyncMock`; assert correct envelope shape and HTTP200 on success and HTTP 422 on validation failure.
- Dev-plan verification: Run `pytest tests/unit/test_enrichment_service.py tests/unit/test_enrichment_router.py -v` and `ruff check src/services/enrichment_service.py src/api/routers/enrichment.py`.

## Acceptance Criteria
- `src/services/enrichment_service.py` passes `ruff check` and `mypy` without errors.
- `src/api/routers/enrichment.py` registers at `/api/v1/enrichment/lookup` in the FastAPI app.
- `EnrichmentService.lookup(domain="stripe.com", provider="clearbit")` returns a `dict` with at least `name` and `domain` when Clearbit responds 200.
- `EnrichmentService.lookup(domain=None, company_name=None)` raises `ValidationException`.
- `EnrichmentService.lookup(domain=None, company_name=None)` when both are provided raises `ValidationException`.
- HTTP404 from Clearbit raises `ValidationException("No company found for the given domain or name")`; other non-2xx raises `ValidationException("Clearbit API error: {status_code}")`.
- `CustomerEnrichmentModel` is inserted into the session on every successful lookup.
- `pytest tests/unit/test_enrichment_service.py tests/unit/test_enrichment_router.py -v` passes with zero test errors.
- No Apollo, ZoomInfo, or other provider code is present in the implementation.
