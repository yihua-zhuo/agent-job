"""Unit tests for src/api/routers/analytics.py — router endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.analytics import analytics_router
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with analytics_router and exception handler."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    app = FastAPI()
    app.include_router(analytics_router)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    return app


# ---------------------------------------------------------------------------
# Module-level mock data fixtures
# ---------------------------------------------------------------------------


REVENUE_DATA = {
    "labels": ["2025-01-01", "2025-01-02"],
    "datasets": [{"label": "Sales Revenue", "data": [1000.0, 2000.0], "color": "#4F46E5"}],
    "chart_type": "line",
}

CONVERSION_DATA = {
    "labels": ["Leads", "Qualified", "Proposal", "Negotiation", "Closed Won"],
    "datasets": [{"label": "Conversion", "data": [50, 30, 20, 10, 5], "color": "#10B981"}],
    "chart_type": "funnel",
}

GROWTH_DATA = {
    "labels": ["New Customers", "Churned", "Net Growth"],
    "datasets": [
        {"label": "Customer Growth", "data": [25, 3, 22], "color": "#F59E0B"},
    ],
    "chart_type": "bar",
}

FORECAST_DATA = {
    "pipeline_id": 1,
    "labels": ["Stage 1", "Stage 2", "Stage 3", "Closed"],
    "datasets": [{"label": "Expected Revenue", "data": [5000.0, 3000.0, 0.0, 0.0], "color": "#8B5CF6"}],
    "chart_type": "bar",
}

TEAM_DATA = {
    "labels": ["Owner 1"],
    "datasets": [
        {"label": "Deals Closed", "data": [5], "color": "#EC4899"},
        {"label": "Revenue", "data": [10000.0], "color": "#3B82F6"},
    ],
    "chart_type": "bar",
}

CHART_DATA = {
    "labels": ["a", "b", "c"],
    "datasets": [{"label": "Data", "data": [1.0, 2.0, 3.0], "color": "#6366F1"}],
    "chart_type": "line",
}


# ---------------------------------------------------------------------------
# Test client fixture (avoids module-level monkeypatch ordering issues)
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_service():
    """Return a TestClient with require_auth and get_db dependency-overridden.

    Dependency overrides are applied before the router is included so there is
    no need to patch AnalyticsService at the class level.
    """
    from db.connection import get_db

    app = _make_app()
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# GET /revenue
# ---------------------------------------------------------------------------


class TestGetSalesRevenue:
    def test_success(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_sales_revenue_report = AsyncMock(return_value=REVENUE_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=day")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "line"
        assert "labels" in body["data"]
        assert "datasets" in body["data"]

    def test_with_group_by_week(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_sales_revenue_report = AsyncMock(return_value=REVENUE_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=week")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_with_group_by_month(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_sales_revenue_report = AsyncMock(return_value=REVENUE_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=month")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_invalid_group_by_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=hour")
        assert resp.status_code == 422

    def test_missing_dates_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/revenue")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /sales-conversion
# ---------------------------------------------------------------------------


class TestGetSalesConversion:
    def test_success(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_sales_conversion_report = AsyncMock(return_value=CONVERSION_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/sales-conversion?start_date=2025-01-01&end_date=2025-01-31")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "funnel"
        assert "labels" in body["data"]

    def test_missing_dates_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/sales-conversion")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /customer-growth
# ---------------------------------------------------------------------------


class TestGetCustomerGrowth:
    def test_success(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_customer_growth_report = AsyncMock(return_value=GROWTH_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/customer-growth?start_date=2025-01-01&end_date=2025-03-31")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "bar"
        assert "labels" in body["data"]

    def test_missing_dates_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/customer-growth")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /pipeline-forecast
# ---------------------------------------------------------------------------


class TestGetPipelineForecast:
    def test_success(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_pipeline_forecast = AsyncMock(return_value=FORECAST_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/pipeline-forecast")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "bar"
        assert "labels" in body["data"]

    def test_with_pipeline_id(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_pipeline_forecast = AsyncMock(return_value=FORECAST_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/pipeline-forecast?pipeline_id=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True


# ---------------------------------------------------------------------------
# GET /team-performance
# ---------------------------------------------------------------------------


class TestGetTeamPerformance:
    def test_success(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_team_performance = AsyncMock(return_value=TEAM_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/team-performance?start_date=2025-01-01&end_date=2025-01-31")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "bar"
        assert len(body["data"]["datasets"]) == 2

    def test_missing_dates_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/team-performance")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /chart-data
# ---------------------------------------------------------------------------


class TestGetChartData:
    def test_success_comma_separated(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_chart_data = MagicMock(return_value=CHART_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get("/api/v1/analytics/chart-data?chart_type=line&data=1,2,3&labels=a,b,c")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["chart_type"] == "line"

    def test_success_json_arrays(self, client_with_service, monkeypatch):
        client = client_with_service
        mock_service = MagicMock()
        mock_service.get_chart_data = MagicMock(return_value=CHART_DATA)
        monkeypatch.setattr(
            "api.routers.analytics.AnalyticsService",
            lambda session: mock_service,
        )
        resp = client.get('/api/v1/analytics/chart-data?chart_type=bar&data=[10,20,30]&labels=["X","Y","Z"]')
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_missing_params_rejected(self, client_with_service):
        client = client_with_service
        resp = client.get("/api/v1/analytics/chart-data?chart_type=line")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth required — all six endpoints must reject unauthenticated requests
# ---------------------------------------------------------------------------


class TestAuthRequired:
    """Plan acceptance criterion: all six endpoints return 401 without a valid token."""

    _ENDPOINTS = [
        ("/api/v1/analytics/revenue", {"start_date": "2025-01-01", "end_date": "2025-01-31"}),
        ("/api/v1/analytics/sales-conversion", {"start_date": "2025-01-01", "end_date": "2025-01-31"}),
        ("/api/v1/analytics/customer-growth", {"start_date": "2025-01-01", "end_date": "2025-01-31"}),
        ("/api/v1/analytics/pipeline-forecast", {}),
        ("/api/v1/analytics/team-performance", {"start_date": "2025-01-01", "end_date": "2025-01-31"}),
        ("/api/v1/analytics/chart-data", {"chart_type": "line", "data": "1,2,3", "labels": "a,b,c"}),
    ]

    def test_revenue_no_auth(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/analytics/revenue", params={"start_date": "2025-01-01", "end_date": "2025-01-31"})
        assert resp.status_code == 401

    def test_revenue_invalid_token(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/analytics/revenue",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize("path,params", _ENDPOINTS)
    def test_all_endpoints_require_auth(self, path, params):
        """Each endpoint returns 401 when no Authorization header is provided."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(path, params=params)
        assert resp.status_code == 401, f"Expected 401 for {path}, got {resp.status_code}"

    @pytest.mark.parametrize("path,params", _ENDPOINTS)
    def test_all_endpoints_reject_invalid_bearer(self, path, params):
        """Each endpoint returns 401 when an invalid token is provided."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            path,
            params=params,
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert resp.status_code == 401, f"Expected 401 for {path}, got {resp.status_code}"
