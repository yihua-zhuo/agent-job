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


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with SalesRecommendationService fully mocked."""
    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.recommendations.SalesRecommendationService",
        lambda session: mock_service,
    )

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

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


class TestGetRecommendations:
    def test_success_returns_200(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(
            return_value={
                "opportunity_id": 5,
                "conversion_probability": 0.72,
                "similar_opportunities": [],
                "next_best_action": {
                    "action": "up_sell",
                    "target": "premium",
                    "reason": "高使用率",
                    "confidence": 0.85,
                },
            }
        )
        resp = client.get("/api/v1/sales/opportunities/5/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["opportunity_id"] == 5
        assert body["data"]["conversion_probability"] == 0.72

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(side_effect=NotFoundException("Opportunity"))
        resp = client.get("/api/v1/sales/opportunities/9999/recommendations")
        assert resp.status_code == 404

    def test_internal_error_returns_500(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(side_effect=RuntimeError("unexpected"))
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 500

    def test_missing_auth_returns_401(self):
        app = FastAPI()
        app.include_router(recommendations_router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        # Do NOT override require_auth — let it reject
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 401
