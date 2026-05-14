# Implementation Plan — Issue #109

## Goal
Add a `MarketingRouter` with full CRUD endpoints (`GET`, `POST`, `GET /{id}`, `PUT/PATCH /{id}`, `DELETE /{id}`) under `/api/v1/marketing/campaigns`, wired to the existing `MarketingService`. Update `main.py` to register the new router and update `src/api/__init__.py` to export it. The existing `CampaignModel` (from `src/db/models/marketing.py`) covers all required fields; the existing `CampaignStatus` and `CampaignType` enums (from `src/models/marketing.py`) need one addition each (`SCHEDULED` status, `SOCIAL` and `ADVERTISING` types).

## Affected Files
- `src/api/routers/marketing.py` — **new** — `APIRouter` with all five CRUD endpoints and request/response schemas
- `src/api/__init__.py` — add `marketing_router` import and export
- `src/main.py` — register `marketing_router` in `create_app()`
- `src/models/marketing.py` — add `SCHEDULED` to `CampaignStatus` enum; add `SOCIAL` and `ADVERTISING` to `CampaignType` enum
- `tests/unit/test_marketing_router.py` — **new** — router endpoint tests using `TestClient` with mocked `MarketingService`
- `tests/integration/test_marketing_integration.py` — **new** — full lifecycle integration tests against real PostgreSQL

## Implementation Steps

1. **Update enums in `src/models/marketing.py`**
   - Add `SCHEDULED = "scheduled"` to `CampaignStatus`
   - Add `SOCIAL = "social"` and `ADVERTISING = "advertising"` to `CampaignType`

2. **Create `src/api/routers/marketing.py`**
   - `marketing_router = APIRouter(prefix="/api/v1/marketing", tags=["marketing"])`
   - Inner `BaseModel` request schemas: `CampaignCreate` (name, type, status, target_audience, start_date, end_date, budget, content, subject), `CampaignUpdate` (all optional), `CampaignPaginationQuery`
   - `GET /campaigns` — list with `page`, `page_size`, `status` query params; calls `svc.list_campaigns()`; returns `_paginated()` wrapper
   - `POST /campaigns` — create; calls `svc.create_campaign()`; returns `{"success": True, "data": campaign.to_dict()}`
   - `GET /campaigns/{campaign_id}` — get single; calls `svc.get_campaign()`; returns wrapped `to_dict()`
   - `PUT /campaigns/{campaign_id}` — full update; calls `svc.update_campaign()`; returns wrapped `to_dict()`
   - `PATCH /campaigns/{campaign_id}` — partial update; calls `svc.update_campaign()` with only non-None fields; returns wrapped `to_dict()`
   - `DELETE /campaigns/{campaign_id}` — delete; calls `svc.delete_campaign()` (add `delete_campaign` to `MarketingService` if needed); returns wrapped `to_dict()`
   - Inject `AuthContext` via `Depends(require_auth)` and `session` via `Depends(get_db)` on every endpoint
   - Use `ctx.tenant_id` and `ctx.user_id` from `AuthContext` when calling service methods

3. **Add `delete_campaign` to `src/services/marketing_service.py`**
   - `delete_campaign(campaign_id, tenant_id)` — fetches via `get_campaign()`, calls `session.delete()`, returns deleted `CampaignModel`
   - Raise `NotFoundException("Campaign")` if not found

4. **Update `src/api/__init__.py`**
   - Import `marketing_router` from `api.routers.marketing`
   - Add `"marketing_router"` to the `__all__` list

5. **Update `src/main.py`**
   - Import `marketing_router` from `api`
   - Add `app.include_router(marketing_router)` after the existing router includes

## Test Plan
- Unit tests in `tests/unit/test_marketing_router.py`: create `client_with_service` fixture (mirrors `test_customers_router.py`), test each endpoint for success response and 404 via `side_effect=NotFoundException`. Use `AsyncMock` for all service methods and `monkeypatch.setattr("api.routers.marketing.MarketingService", lambda session: mock_service)`. Cover: list (pagination, status filter), create, get, update (PUT), partial update (PATCH), delete, not-found on every endpoint.
- Integration tests in `tests/integration/test_marketing_integration.py`: create `TestMarketingServiceIntegration` with `@pytest.mark.integration`. Full lifecycle: create → get → update → list (filter by status) → delete. Use `uuid.uuid4().hex[:8]` suffix on all campaign names. Assert `pytest.raises(NotFoundException)` on get/update/delete after deletion. Import `MarketingService` from `services.marketing_service`.

## Acceptance Criteria
- `GET /api/v1/marketing/campaigns` returns `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20}}`
- `POST /api/v1/marketing/campaigns` returns 201 with `{"success": true, "data": {...}}` containing the created campaign
- `GET /api/v1/marketing/campaigns/{id}` returns the campaign or 404 via `NotFoundException`
- `PUT /api/v1/marketing/campaigns/{id}` replaces the campaign; `PATCH` merges only supplied fields
- `DELETE /api/v1/marketing/campaigns/{id}` returns 200 and the campaign is no longer fetchable
- All endpoints enforce tenant isolation via `tenant_id` from `AuthContext`
- OpenAPI spec at `/openapi.json` includes all five new paths under `marketing` tag
