"""Unit tests for src/api/routers/sales.py — typed response schemas and _http_status."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from api.routers.sales import (
    sales_router,
    _http_status,
)
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_service_response(status=ResponseStatus.SUCCESS, data=None, message="OK"):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    resp.message = message
    return resp


PIPELINE_ROW = {
    "id": 1,
    "tenant_id": 1,
    "name": "Sales Pipeline",
    "stages": ["lead", "qualified"],
    "is_default": True,
    "created_at": None,
    "updated_at": None,
}

OPPORTUNITY_ROW = {
    "id": 1,
    "tenant_id": 1,
    "name": "Big Deal",
    "customer_id": 10,
    "pipeline_id": 1,
    "stage": "qualified",
    "amount": "5000.00",
    "probability": 50,
    "expected_close_date": None,
    "owner_id": 1,
    "created_at": None,
    "updated_at": None,
}

LIST_DATA_PIPELINE = {
    "items": [PIPELINE_ROW],
}

LIST_DATA_OPP = {
    "items": [OPPORTUNITY_ROW],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "has_next": False,
    "has_prev": False,
}


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with SalesService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.sales.SalesService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(sales_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# _http_status (sales router version)
# ---------------------------------------------------------------------------

class TestSalesHttpStatus:
    def test_success_returns_200(self):
        assert _http_status(ResponseStatus.SUCCESS) == 200

    def test_warning_returns_200(self):
        assert _http_status(ResponseStatus.WARNING) == 200

    def test_not_found_returns_404(self):
        assert _http_status(ResponseStatus.NOT_FOUND) == 404

    def test_validation_error_returns_400(self):
        assert _http_status(ResponseStatus.VALIDATION_ERROR) == 400

    def test_unauthorized_returns_401(self):
        assert _http_status(ResponseStatus.UNAUTHORIZED) == 401

    def test_forbidden_returns_403(self):
        assert _http_status(ResponseStatus.FORBIDDEN) == 403

    def test_server_error_returns_500(self):
        assert _http_status(ResponseStatus.SERVER_ERROR) == 500

    def test_error_returns_400(self):
        assert _http_status(ResponseStatus.ERROR) == 400

    def test_unknown_status_returns_400(self):
        unknown = MagicMock()
        assert _http_status(unknown) == 400


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

class TestCreatePipelineEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_pipeline = AsyncMock(
            return_value=_make_service_response(data=PIPELINE_ROW, message="Pipeline created")
        )
        resp = client.post(
            "/api/v1/sales/pipelines",
            json={"name": "Sales Pipeline", "is_default": True, "stages": ["lead"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Sales Pipeline"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_pipeline = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR, message="Invalid"
            )
        )
        resp = client.post(
            "/api/v1/sales/pipelines",
            json={"name": "X", "is_default": False},
        )
        assert resp.status_code == 400

    def test_empty_name_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/sales/pipelines",
            json={"name": ""},
        )
        assert resp.status_code == 422

    def test_name_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/sales/pipelines",
            json={"name": "x" * 201},
        )
        assert resp.status_code == 422


class TestListPipelinesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.list_pipelines = AsyncMock(
            return_value=_make_service_response(data=LIST_DATA_PIPELINE, message="OK")
        )
        resp = client.get("/api/v1/sales/pipelines")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_empty_list(self, client_with_service):
        client, svc = client_with_service
        svc.list_pipelines = AsyncMock(
            return_value=_make_service_response(data={"items": []}, message="OK")
        )
        resp = client.get("/api/v1/sales/pipelines")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


class TestGetPipelineEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.get_pipeline = AsyncMock(
            return_value=_make_service_response(data=PIPELINE_ROW, message="OK")
        )
        resp = client.get("/api/v1/sales/pipelines/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_pipeline = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.get("/api/v1/sales/pipelines/9999")
        assert resp.status_code == 404


class TestGetPipelineStatsEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        stats_data = {"pipeline_id": 1, "total": 10, "won": 3, "lost": 2}
        svc.get_pipeline_stats = AsyncMock(
            return_value=_make_service_response(data=stats_data, message="OK")
        )
        resp = client.get("/api/v1/sales/pipelines/1/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 10
        assert body["data"]["won"] == 3

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_pipeline_stats = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.get("/api/v1/sales/pipelines/9999/stats")
        assert resp.status_code == 404


class TestGetPipelineFunnelEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        funnel_data = {"pipeline_id": 1, "stages": [{"name": "lead", "count": 5}]}
        svc.get_pipeline_funnel = AsyncMock(
            return_value=_make_service_response(data=funnel_data, message="OK")
        )
        resp = client.get("/api/v1/sales/pipelines/1/funnel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["pipeline_id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_pipeline_funnel = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.get("/api/v1/sales/pipelines/9999/funnel")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Opportunity endpoints
# ---------------------------------------------------------------------------

class TestCreateOpportunityEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_opportunity = AsyncMock(
            return_value=_make_service_response(data=OPPORTUNITY_ROW, message="Opp created")
        )
        resp = client.post(
            "/api/v1/sales/opportunities",
            json={
                "name": "Big Deal",
                "customer_id": 10,
                "pipeline_id": 1,
                "stage": "qualified",
                "amount": 5000.0,
                "owner_id": 1,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Big Deal"

    def test_close_date_remapped_to_expected_close_date(self, client_with_service):
        """Verify the close_date → expected_close_date remapping happens in the endpoint."""
        client, svc = client_with_service
        captured = {}

        async def capture_create(tenant_id, data):
            captured["data"] = data
            return _make_service_response(data=OPPORTUNITY_ROW)

        svc.create_opportunity = capture_create
        resp = client.post(
            "/api/v1/sales/opportunities",
            json={
                "name": "Deal",
                "customer_id": 1,
                "pipeline_id": 1,
                "stage": "lead",
                "amount": 100.0,
                "owner_id": 1,
                "close_date": "2025-12-31",
            },
        )
        assert resp.status_code == 201
        assert "expected_close_date" in captured["data"]
        assert "close_date" not in captured["data"]

    def test_missing_required_fields_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/sales/opportunities",
            json={"name": "Incomplete"},
        )
        assert resp.status_code == 422

    def test_negative_amount_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/sales/opportunities",
            json={
                "name": "Deal",
                "customer_id": 1,
                "pipeline_id": 1,
                "stage": "lead",
                "amount": -1.0,
                "owner_id": 1,
            },
        )
        assert resp.status_code == 422

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_opportunity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR, message="Invalid"
            )
        )
        resp = client.post(
            "/api/v1/sales/opportunities",
            json={
                "name": "Deal",
                "customer_id": 1,
                "pipeline_id": 1,
                "stage": "lead",
                "amount": 100.0,
                "owner_id": 1,
            },
        )
        assert resp.status_code == 400


class TestListOpportunitiesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.list_opportunities = AsyncMock(
            return_value=_make_service_response(data=LIST_DATA_OPP, message="OK")
        )
        resp = client.get("/api/v1/sales/opportunities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1

    def test_with_filters(self, client_with_service):
        client, svc = client_with_service
        svc.list_opportunities = AsyncMock(
            return_value=_make_service_response(data=LIST_DATA_OPP, message="OK")
        )
        resp = client.get("/api/v1/sales/opportunities?pipeline_id=1&stage=lead&owner_id=1")
        assert resp.status_code == 200

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/sales/opportunities?page_size=101")
        assert resp.status_code == 422


class TestGetOpportunityEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.get_opportunity = AsyncMock(
            return_value=_make_service_response(data=OPPORTUNITY_ROW, message="OK")
        )
        resp = client.get("/api/v1/sales/opportunities/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_opportunity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.get("/api/v1/sales/opportunities/9999")
        assert resp.status_code == 404


class TestUpdateOpportunityEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.update_opportunity = AsyncMock(
            return_value=_make_service_response(
                data={**OPPORTUNITY_ROW, "name": "Updated"}, message="Updated"
            )
        )
        resp = client.put("/api/v1/sales/opportunities/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated"

    def test_close_date_remapped(self, client_with_service):
        client, svc = client_with_service
        captured = {}

        async def capture_update(tenant_id, opp_id, data):
            captured["data"] = data
            return _make_service_response(data=OPPORTUNITY_ROW)

        svc.update_opportunity = capture_update
        resp = client.put(
            "/api/v1/sales/opportunities/1",
            json={"close_date": "2025-06-30"},
        )
        assert resp.status_code == 200
        assert "expected_close_date" in captured["data"]
        assert "close_date" not in captured["data"]

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_opportunity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.put("/api/v1/sales/opportunities/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestChangeStageEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.change_stage = AsyncMock(
            return_value=_make_service_response(
                data={"id": 1, "stage": "closed"}, message="Stage changed"
            )
        )
        resp = client.put(
            "/api/v1/sales/opportunities/1/stage",
            json={"stage": "closed"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["stage"] == "closed"

    def test_empty_stage_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.put("/api/v1/sales/opportunities/1/stage", json={"stage": ""})
        assert resp.status_code == 422

    def test_stage_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.put(
            "/api/v1/sales/opportunities/1/stage",
            json={"stage": "x" * 51},
        )
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.change_stage = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="Not found"
            )
        )
        resp = client.put(
            "/api/v1/sales/opportunities/9999/stage",
            json={"stage": "closed"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Forecast endpoint
# ---------------------------------------------------------------------------

class TestGetForecastEndpoint:
    def test_success_no_owner(self, client_with_service):
        client, svc = client_with_service
        svc.get_forecast = AsyncMock(
            return_value=_make_service_response(
                data={"owner_id": None, "forecast": {"total": 9000}}, message="OK"
            )
        )
        resp = client.get("/api/v1/sales/forecast")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["forecast"]["total"] == 9000

    def test_success_with_owner_id(self, client_with_service):
        client, svc = client_with_service
        svc.get_forecast = AsyncMock(
            return_value=_make_service_response(
                data={"owner_id": 3, "forecast": {"q1": 5000}}, message="OK"
            )
        )
        resp = client.get("/api/v1/sales/forecast?owner_id=3")
        assert resp.status_code == 200
        assert resp.json()["data"]["owner_id"] == 3

    def test_negative_owner_id_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/sales/forecast?owner_id=-1")
        assert resp.status_code == 422