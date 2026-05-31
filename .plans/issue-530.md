Now I have a complete picture of the codebase. Let me write the implementation plan.

# Implementation Plan — Issue #530

## Goal

Add the missing `GET /api/v1/marketing/campaigns/{campaign_id}/stats` endpoint to `src/api/routers/marketing.py` and its unit test coverage. The rest of the required endpoints (list, get, create, update/PUT, update/PATCH, delete) and their tests already exist — this board's actual scope is the stats endpoint only.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0530-add-campaign-router-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0530-add-campaign-router-endpoints.md`

## Affected Files

- `src/api/routers/marketing.py` — add `GET /api/v1/marketing/campaigns/{campaign_id}/stats` endpoint
- `tests/unit/test_marketing_router.py` — add `TestGetCampaignStatsEndpoint` test class

## Implementation Steps

1. **Add stats endpoint to `src/api/routers/marketing.py`**

   After the `delete_campaign` endpoint (line ~157), add:
   ```python
   @marketing_router.get("/campaigns/{campaign_id}/stats")
   async def get_campaign_stats(
       campaign_id: int,
       ctx: AuthContext = Depends(require_auth),
       session: AsyncSession = Depends(get_db),
   ):
       svc = MarketingService(session)
       stats = await svc.get_campaign_stats(campaign_id, tenant_id=ctx.tenant_id)
       return {"success": True, "data": stats}
   ```

   The service method `get_campaign_stats` (already at `src/services/marketing_service.py` L100) returns a dict with `campaign_id`, `sent_count`, `open_count`, `click_count`, `open_rate`, `click_rate` — no `.to_dict()` needed.

   **完成判定**: `ruff check src/api/routers/marketing.py` exits 0.

2. **Add stats unit tests to `tests/unit/test_marketing_router.py`**

   Add a new test class at the end of the file:
   ```python
   class TestGetCampaignStatsEndpoint:
       def test_success(self, client_with_service):
           client, svc = client_with_service
           svc.get_campaign_stats = AsyncMock(return_value={
               "campaign_id": 1, "sent_count": 100, "open_count": 40,
               "click_count": 10, "open_rate": 40.0, "click_rate": 10.0,
           })
           resp = client.get("/api/v1/marketing/campaigns/1/stats")
           assert resp.status_code == 200
           body = resp.json()
           assert body["success"] is True
           assert body["data"]["sent_count"] == 100
           assert body["data"]["open_rate"] == 40.0

       def test_not_found_returns_404(self, client_with_service):
           client, svc = client_with_service
           svc.get_campaign_stats = AsyncMock(side_effect=NotFoundException("Campaign"))
           resp = client.get("/api/v1/marketing/campaigns/9999/stats")
           assert resp.status_code == 404
   ```

   The fixture `client_with_service` (already in the file at L41) mocks `MarketingService` entirely via `monkeypatch.setattr("api.routers.marketing.MarketingService", ...)`, so no fixture changes are needed.

   **完成判定**: `PYTHONPATH=src pytest tests/unit/test_marketing_router.py::TestGetCampaignStatsEndpoint -v` → 2 passed.

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_marketing_router.py` — add `TestGetCampaignStatsEndpoint` with 2 cases (happy path + 404). All other router endpoints are already covered in the same file.
- **Integration tests in `tests/integration/`**: `tests/integration/test_marketing_integration.py` already tests `MarketingService.get_campaign_stats` indirectly via the service-level test suite. Router-level integration for stats is deferred to #531 per the dev-plan.
- **Dev-plan verification**:
  - `ruff check src/api/routers/marketing.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_marketing_router.py -v` → all passed (includes new stats cases)
  - `PYTHONPATH=src pytest tests/integration/test_marketing_integration.py -v` → all passed (service-level coverage; router-level deferred to #531)

## Acceptance Criteria

- `ruff check src/api/routers/marketing.py tests/unit/test_marketing_router.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_marketing_router.py -v` → all passed including new `TestGetCampaignStatsEndpoint` cases
- `GET /api/v1/marketing/campaigns/{id}/stats` returns `{"success": true, "data": {"campaign_id": ..., "sent_count": ..., "open_count": ..., "click_count": ..., "open_rate": ..., "click_rate": ...}}` with HTTP 200
- `GET /api/v1/marketing/campaigns/{nonexistent}/stats` returns HTTP 404 via `NotFoundException` propagated from the service
