"""Unit tests for src/api/routers/recommendations.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.exception_handlers import register_exception_handlers
from api.routers.recommendations import recommendations_router
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import NotFoundException
from services.recommendation_service import CachedRecommendationResult
from services.sales_recommendation import SalesActionRecommendation


def _make_auth_ctx(tenant_id: int | None = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _build_app(auth_ctx: AuthContext | None = None) -> FastAPI:
    """Build app with dependency overrides. Pass `auth_ctx=None` to test 401 path."""
    app = FastAPI()
    app.include_router(recommendations_router)
    register_exception_handlers(app)

    if auth_ctx is not None:
        app.dependency_overrides[require_auth] = lambda: auth_ctx
    return app


@pytest.fixture
def mocked_service_client(monkeypatch):
    """Return a TestClient with RecommendationService fully mocked."""
    mock_service = SimpleNamespace(
        get_recommendations=AsyncMock(
            return_value=CachedRecommendationResult(
                opportunity_id=5,
                conversion_probability=0.72,
                next_best_action=SalesActionRecommendation(
                    action="up_sell",
                    target="premium",
                    reason="高使用率",
                    confidence=0.85,
                ),
                similar_opportunities=[],
            )
        )
    )
    monkeypatch.setattr(
        "api.routers.recommendations.RecommendationService",
        lambda session: mock_service,
    )
    app = _build_app(auth_ctx=_make_auth_ctx())
    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


@pytest.fixture
def no_auth_client():
    """Return a TestClient where require_auth is NOT overridden (to test 401)."""
    app = _build_app(auth_ctx=None)
    return TestClient(app, raise_server_exceptions=False)


class TestGetRecommendations:
    def test_success_returns_200(self, mocked_service_client):
        client, svc = mocked_service_client
        resp = client.get("/api/v1/sales/opportunities/5/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["opportunity_id"] == 5
        assert body["data"]["conversion_probability"] == 0.72
        assert body["data"]["next_best_action"]["action"] == "up_sell"
        assert body["data"]["next_best_action"]["target"] == "premium"
        assert body["data"]["similar_opportunities"] == []
        svc.get_recommendations.assert_awaited_once_with(5, 1)

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

    def test_missing_tenant_returns_422(self, mocked_service_client):
        client, svc = mocked_service_client
        svc.get_recommendations = AsyncMock(return_value=mocked_service_client[1].get_recommendations.return_value)
        # Override auth to return a context with tenant_id = None
        client.app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=None)
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 422
        svc.get_recommendations.assert_not_called()

    def test_missing_auth_returns_401(self, no_auth_client):
        client = no_auth_client
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 401

    @pytest.mark.parametrize("opportunity_id", [0, -1, 9999999999])
    def test_path_param_extremes_are_routed(self, mocked_service_client, opportunity_id):
        client, _ = mocked_service_client
        resp = client.get(f"/api/v1/sales/opportunities/{opportunity_id}/recommendations")
        # FastAPI accepts any int; the service handles the lookup outcome (200/404).
        assert resp.status_code in (200, 404)
