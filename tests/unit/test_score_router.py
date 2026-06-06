"""Unit tests for the /score endpoints mounted on the customers router."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.customers import customers_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from models.score import ScoreTier
from pkg.errors.app_exceptions import AppException, NotFoundException
from services.score_service import ScoreResult


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _register_app_exception_handler(app: FastAPI) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail},
        )


def _build_score_test_app(monkeypatch, *, override_score: bool = True, override_auth: bool = True):
    """Build a TestClient for the score endpoints with CustomerService and ScoreService mocked.

    Returns (client, customer_mock, score_mock). A single score_mock instance is reused
    across all requests in the test (router calls ScoreService(session) per request, but
    the override returns the same mock each time). Tests reassign the relevant method
    on score_mock before each request to avoid state leaking between tests.
    """
    from internal.middleware.fastapi_auth import require_auth

    customer_mock = MagicMock()
    score_mock = MagicMock()

    def override_customer_service(repository):
        return customer_mock

    def override_score_service(session):
        return score_mock

    mock_session = MagicMock()
    mock_enrich_result = MagicMock()
    mock_enrich_result.all = MagicMock(return_value=[])
    mock_enrich_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_enrich_result)

    app = FastAPI()
    app.include_router(customers_router)
    if override_auth:
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_session

    monkeypatch.setattr(
        "api.routers.customers.CustomerService",
        override_customer_service,
    )
    if override_score:
        monkeypatch.setattr(
            "api.routers.customers.ScoreService",
            override_score_service,
        )

    monkeypatch.setattr(
        "api.routers.customers.CustomerRepository",
        lambda session: MagicMock(session=session),
    )

    _register_app_exception_handler(app)

    client = TestClient(app, raise_server_exceptions=False)
    return client, customer_mock, score_mock


@pytest.fixture
def client_with_score_service(monkeypatch):
    client, cust_mock, score_mock = _build_score_test_app(monkeypatch)
    return client, cust_mock, score_mock


class TestScoreEndpoints:
    def test_post_score_returns_data(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.calculate_score = AsyncMock(
            return_value=ScoreResult(
                score=85,
                tier=ScoreTier.B,
                top_factors=["engagement_level"],
                recommendations=["Increase touchpoints with targeted campaigns"],
                similar_leads=[],
            )
        )
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["score"] == 85
        assert body["data"]["tier"] == "B"
        assert body["data"]["top_factors"] == ["engagement_level"]
        assert body["data"]["recommendations"] == ["Increase touchpoints with targeted campaigns"]
        assert "message" in body
        score_svc.calculate_score.assert_called_once_with(1, tenant_id=1, include_ai=True)

    def test_get_score_returns_data_with_factors(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(
            return_value=ScoreResult(
                score=75,
                tier=ScoreTier.B,
                top_factors=["deal_velocity"],
                recommendations=["Accelerate pipeline with limited-time offers"],
                similar_leads=[],
            )
        )
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["score"] == 75
        assert body["data"]["tier"] == "B"
        assert body["data"]["top_factors"] == ["deal_velocity"]
        assert body["data"]["recommendations"] == ["Accelerate pipeline with limited-time offers"]

    def test_get_score_returns_404_when_no_score(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(side_effect=NotFoundException("Score"))
        resp = client.get("/api/v1/customers/9999/score")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "Score" in body["message"]

    def test_get_score_returns_404_when_customer_missing(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.get("/api/v1/customers/9999/score")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "Customer" in body["message"]

    def test_post_score_requires_auth(self, monkeypatch):
        client, _cust, _ = _build_score_test_app(monkeypatch, override_auth=False)
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    def test_get_score_requires_auth(self, monkeypatch):
        client, _cust, _ = _build_score_test_app(monkeypatch, override_auth=False)
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
