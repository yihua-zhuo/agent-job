"""Unit tests for src/api/routers/recommendations.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.recommendations import recommendations_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException
from services.sales_recommendation import RecommendationResult, SalesActionRecommendation


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _build_app(mock_service: MagicMock | None) -> FastAPI:
    """Build a FastAPI app with the router, the global exception handlers from
    main.py, and dependency overrides. `mock_service=None` means do not patch
    the service (used for tests that exercise auth only)."""
    app = FastAPI()
    app.include_router(recommendations_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error", "code": "INTERNAL_ERROR"},
        )

    return app


@pytest.fixture
def mocked_service_client(monkeypatch):
    """Return a TestClient with SalesRecommendationService fully mocked."""
    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.recommendations.SalesRecommendationService",
        lambda: mock_service,
    )
    app = _build_app(mock_service)
    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


@pytest.fixture
def no_auth_client():
    """Return a TestClient where require_auth is NOT overridden (to test 401)."""
    app = FastAPI()
    app.include_router(recommendations_router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _make_recommendation_result(
    opportunity_id: int = 5,
    conversion_probability: float = 0.72,
) -> RecommendationResult:
    return RecommendationResult(
        opportunity_id=opportunity_id,
        conversion_probability=conversion_probability,
        similar_opportunities=[],
        next_best_action=SalesActionRecommendation(
            action="up_sell",
            target="premium",
            reason="高使用率",
            confidence=0.85,
        ),
    )


class TestGetRecommendations:
    def test_success_returns_200(self, mocked_service_client):
        client, svc = mocked_service_client
        svc.get_recommendations = AsyncMock(return_value=_make_recommendation_result())
        resp = client.get("/api/v1/sales/opportunities/5/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Recommendations fetched"
        assert body["data"]["opportunity_id"] == 5
        assert body["data"]["conversion_probability"] == 0.72

    def test_not_found_returns_404(self, mocked_service_client):
        client, svc = mocked_service_client
        svc.get_recommendations = AsyncMock(side_effect=NotFoundException("Opportunity"))
        resp = client.get("/api/v1/sales/opportunities/9999/recommendations")
        assert resp.status_code == 404

    def test_internal_error_returns_500(self, mocked_service_client):
        client, svc = mocked_service_client
        svc.get_recommendations = AsyncMock(side_effect=RuntimeError("unexpected"))
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "INTERNAL_ERROR"

    def test_missing_tenant_returns_400(self, monkeypatch):
        from api.routers import recommendations as rec_router

        mock_service = MagicMock()
        mock_service.get_recommendations = AsyncMock(return_value=_make_recommendation_result())
        monkeypatch.setattr(rec_router, "SalesRecommendationService", lambda: mock_service)

        app = _build_app(mock_service)
        # Override auth to return a context with tenant_id = None
        app.dependency_overrides[require_auth] = lambda: AuthContext(user_id=99, tenant_id=None, roles=[])
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 400
        mock_service.get_recommendations.assert_not_called()

    def test_missing_auth_returns_401(self, no_auth_client):
        client = no_auth_client
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 401
