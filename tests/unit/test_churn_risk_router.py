"""Unit tests for src/api/routers/churn_risk.py."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.churn_risk import churn_risk_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import AppException, NotFoundException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_prediction(customer_id: int = 42, score: float = 75.0, tier: str = "high"):
    """Build a mock ChurnPrediction-like object with __dict__/fields."""
    from dataclasses import dataclass, field

    @dataclass
    class _Factor:
        name: str
        weight: float
        score: float
        description: str

    @dataclass
    class _Prediction:
        customer_id: int
        score: float
        tier: str
        top_3_risk_factors: list = field(default_factory=list)
        recommended_actions: list = field(default_factory=list)

    return _Prediction(
        customer_id=customer_id,
        score=score,
        tier=tier,
        top_3_risk_factors=[
            _Factor(name="login_frequency", weight=0.25, score=40.0, description="login frequency in the last 30 days"),
        ],
        recommended_actions=["客户登录频率低，建议发送个性化内容激活"],
    )


@pytest.fixture
def mock_db_session():
    """Minimal mock DB session — not used directly because ChurnPredictionService is patched."""
    return AsyncMock()


@pytest.fixture
def client(monkeypatch, mock_db_session):
    """Return a TestClient with ChurnPredictionService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth

    mock_service = AsyncMock()

    monkeypatch.setattr(
        "api.routers.churn_risk.ChurnPredictionService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(churn_risk_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_db_session

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"success": False, "message": "Validation error", "detail": exc.errors()},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


class TestGetChurnRisk:
    def test_returns_existing_prediction(self, client):
        c, svc = client
        prediction = _make_prediction(customer_id=42, score=82.5, tier="high")
        svc.calculate_score = AsyncMock(return_value=prediction)

        resp = c.get("/api/v1/customers/42/churn-risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["customer_id"] == 42
        assert body["data"]["score"] == 82.5
        assert body["data"]["tier"] == "high"
        assert "top_3_risk_factors" in body["data"]
        assert "recommended_actions" in body["data"]
        svc.calculate_score.assert_awaited_once_with(42, tenant_id=1)

    def test_returns_low_tier_prediction(self, client):
        c, svc = client
        prediction = _make_prediction(customer_id=7, score=15.0, tier="low")
        svc.calculate_score = AsyncMock(return_value=prediction)

        resp = c.get("/api/v1/customers/7/churn-risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tier"] == "low"
        assert body["data"]["score"] == 15.0
        assert body["data"]["customer_id"] == 7

    def test_not_found_returns_404(self, client):
        c, svc = client
        svc.calculate_score = AsyncMock(side_effect=NotFoundException("Customer"))

        resp = c.get("/api/v1/customers/9999/churn-risk")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "NOT_FOUND"
        assert "not found" in body["message"].lower()


class TestPredictBatch:
    def test_returns_predictions(self, client):
        c, svc = client
        p1 = _make_prediction(customer_id=1, score=70.0, tier="high")
        p2 = _make_prediction(customer_id=2, score=30.0, tier="low")
        svc.calculate_score = AsyncMock(side_effect=[p1, p2])

        resp = c.post("/api/v1/customers/churn-predict-batch", json={"customer_ids": [1, 2]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["predictions"]) == 2
        assert body["data"]["predictions"][0]["customer_id"] == 1
        assert body["data"]["predictions"][0]["tier"] == "high"
        assert body["data"]["predictions"][1]["customer_id"] == 2
        assert body["data"]["predictions"][1]["tier"] == "low"

    def test_empty_list_rejected(self, client):
        c, _svc = client
        resp = c.post("/api/v1/customers/churn-predict-batch", json={"customer_ids": []})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False

    def test_oversized_batch_rejected(self, client):
        c, _svc = client
        resp = c.post(
            "/api/v1/customers/churn-predict-batch",
            json={"customer_ids": list(range(1, 502))},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False

    def test_passes_tenant_id(self, client):
        c, svc = client
        prediction = _make_prediction(customer_id=5, score=50.0, tier="medium")
        svc.calculate_score = AsyncMock(return_value=prediction)

        resp = c.post("/api/v1/customers/churn-predict-batch", json={"customer_ids": [5]})
        assert resp.status_code == 200
        svc.calculate_score.assert_awaited_once_with(5, tenant_id=1)
