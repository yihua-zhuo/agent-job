"""Unit tests for src/api/routers/marketing.py — router endpoint tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routers.marketing import marketing_router
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db
from pkg.errors.app_exceptions import NotFoundException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


CAMPAIGN_ROW = {
    "id": 1,
    "tenant_id": 1,
    "name": "Summer Sale",
    "type": "email",
    "status": "draft",
    "subject": "Summer Sale!",
    "content": "Check out our deals",
    "target_audience": "all_users",
    "trigger_type": None,
    "trigger_days": None,
    "created_by": 99,
    "sent_count": 0,
    "open_count": 0,
    "click_count": 0,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
}


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with MarketingService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from pkg.errors.app_exceptions import AppException

    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.marketing.MarketingService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(marketing_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListCampaignsEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = CAMPAIGN_ROW
        svc.list_campaigns = AsyncMock(return_value=([mock_campaign], 1))
        resp = client.get("/api/v1/marketing/campaigns")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_pagination_params(self, client_with_service):
        client, svc = client_with_service
        svc.list_campaigns = AsyncMock(return_value=([], 10))
        resp = client.get("/api/v1/marketing/campaigns?page=2&page_size=5")
        assert resp.status_code == 200
        assert resp.json()["data"]["page"] == 2
        assert resp.json()["data"]["page_size"] == 5

    def test_status_filter(self, client_with_service):
        client, svc = client_with_service
        svc.list_campaigns = AsyncMock(return_value=([], 0))
        resp = client.get("/api/v1/marketing/campaigns?status=active")
        assert resp.status_code == 200
        svc.list_campaigns.assert_called_once()
        call_kwargs = svc.list_campaigns.call_args.kwargs
        assert call_kwargs["status"] == "active"

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/marketing/campaigns?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateCampaignEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = CAMPAIGN_ROW
        svc.create_campaign = AsyncMock(return_value=mock_campaign)
        resp = client.post(
            "/api/v1/marketing/campaigns",
            json={"name": "Summer Sale", "type": "email", "content": "Check out deals"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Summer Sale"

    def test_not_found_if_service_raises(self, client_with_service):
        client, svc = client_with_service
        svc.create_campaign = AsyncMock(side_effect=NotFoundException("Campaign"))
        resp = client.post(
            "/api/v1/marketing/campaigns",
            json={"name": "Bad", "type": "email", "content": ""},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

class TestGetCampaignEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = CAMPAIGN_ROW
        svc.get_campaign = AsyncMock(return_value=mock_campaign)
        resp = client.get("/api/v1/marketing/campaigns/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_campaign = AsyncMock(side_effect=NotFoundException("Campaign"))
        resp = client.get("/api/v1/marketing/campaigns/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update (PUT)
# ---------------------------------------------------------------------------

class TestUpdateCampaignPutEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated = {**CAMPAIGN_ROW, "name": "Updated Campaign"}
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = updated
        svc.update_campaign = AsyncMock(return_value=mock_campaign)
        resp = client.put("/api/v1/marketing/campaigns/1", json={"name": "Updated Campaign"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Campaign"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_campaign = AsyncMock(side_effect=NotFoundException("Campaign"))
        resp = client.put("/api/v1/marketing/campaigns/9999", json={"name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update (PATCH)
# ---------------------------------------------------------------------------

class TestUpdateCampaignPatchEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated = {**CAMPAIGN_ROW, "status": "active"}
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = updated
        svc.update_campaign = AsyncMock(return_value=mock_campaign)
        resp = client.patch("/api/v1/marketing/campaigns/1", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_campaign = AsyncMock(side_effect=NotFoundException("Campaign"))
        resp = client.patch("/api/v1/marketing/campaigns/9999", json={"status": "active"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteCampaignEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_campaign = MagicMock()
        mock_campaign.to_dict.return_value = CAMPAIGN_ROW
        svc.delete_campaign = AsyncMock(return_value=mock_campaign)
        resp = client.delete("/api/v1/marketing/campaigns/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_campaign = AsyncMock(side_effect=NotFoundException("Campaign"))
        resp = client.delete("/api/v1/marketing/campaigns/9999")
        assert resp.status_code == 404