"""Unit tests for src/api/routers/churn_risk.py."""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.churn_risk import churn_risk_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


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

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "score": self.score,
            "tier": self.tier,
            "top_3_risk_factors": [f.__dict__ for f in self.top_3_risk_factors],
            "recommended_actions": list(self.recommended_actions),
        }


def _make_prediction(customer_id: int = 42, score: float = 75.0, tier: str = "high") -> _Prediction:
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
def mock_churn_service():
    return AsyncMock()


@pytest.fixture
def client(mock_churn_service):
    """TestClient for the churn risk router with the service fully mocked."""
    from api.routers import churn_risk

    monkeypatch_module = churn_risk
    original = monkeypatch_module.ChurnPredictionService
    monkeypatch_module.ChurnPredictionService = lambda session: mock_churn_service

    app = FastAPI()
    app.include_router(churn_risk_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: AsyncMock()

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

    test_client = TestClient(app, raise_server_exceptions=False)

    yield test_client

    monkeypatch_module.ChurnPredictionService = original


class TestGetChurnRisk:
    def test_returns_stored_prediction(self, client, mock_churn_service):
        prediction = _make_prediction(customer_id=42, score=82.5, tier="high")
        mock_churn_service.get_churn_prediction = AsyncMock(return_value=prediction)
        mock_churn_service.calculate_score = AsyncMock()

        resp = client.get("/api/v1/customers/42/churn-risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["customer_id"] == 42
        assert body["data"]["score"] == 82.5
        assert body["data"]["tier"] == "high"
        assert "top_3_risk_factors" in body["data"]
        assert "recommended_actions" in body["data"]
        mock_churn_service.get_churn_prediction.assert_awaited_once_with(42, tenant_id=1)
        mock_churn_service.calculate_score.assert_not_awaited()

    def test_falls_back_to_compute_on_not_found(self, client, mock_churn_service):
        prediction = _make_prediction(customer_id=7, score=15.0, tier="low")
        mock_churn_service.get_churn_prediction = AsyncMock(side_effect=NotFoundException("ChurnPrediction"))
        mock_churn_service.calculate_score = AsyncMock(return_value=prediction)

        resp = client.get("/api/v1/customers/7/churn-risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tier"] == "low"
        assert body["data"]["score"] == 15.0
        assert body["data"]["customer_id"] == 7
        mock_churn_service.get_churn_prediction.assert_awaited_once_with(7, tenant_id=1)
        mock_churn_service.calculate_score.assert_awaited_once_with(7, tenant_id=1)

    def test_not_found_returns_404(self, client, mock_churn_service):
        mock_churn_service.get_churn_prediction = AsyncMock(side_effect=NotFoundException("ChurnPrediction"))
        mock_churn_service.calculate_score = AsyncMock(side_effect=NotFoundException("Customer"))

        resp = client.get("/api/v1/customers/9999/churn-risk")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "NOT_FOUND"
        assert "not found" in body["message"].lower()


class TestPredictBatch:
    def test_returns_predictions(self, client, mock_churn_service):
        p1 = _make_prediction(customer_id=1, score=70.0, tier="high")
        p2 = _make_prediction(customer_id=2, score=30.0, tier="low")
        mock_churn_service.predict_churn = AsyncMock(return_value=[p1, p2])

        resp = client.post("/api/v1/customers/churn-predict-batch", json={"customer_ids": [1, 2]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["predictions"]) == 2
        assert body["data"]["predictions"][0]["customer_id"] == 1
        assert body["data"]["predictions"][0]["tier"] == "high"
        assert body["data"]["predictions"][1]["customer_id"] == 2
        assert body["data"]["predictions"][1]["tier"] == "low"
        mock_churn_service.predict_churn.assert_awaited_once_with([1, 2], tenant_id=1)

    def test_batch_skips_not_found_customers(self, client, mock_churn_service):
        p1 = _make_prediction(customer_id=1, score=70.0, tier="high")
        p2 = _make_prediction(customer_id=2, score=30.0, tier="low")
        mock_churn_service.predict_churn = AsyncMock(return_value=[p1, p2])

        resp = client.post(
            "/api/v1/customers/churn-predict-batch",
            json={"customer_ids": [1, 2, 3]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["predictions"]) == 2
        returned_ids = [p["customer_id"] for p in body["data"]["predictions"]]
        assert 1 in returned_ids
        assert 2 in returned_ids
        assert 3 not in returned_ids
        mock_churn_service.predict_churn.assert_awaited_once_with([1, 2, 3], tenant_id=1)

    def test_empty_list_rejected(self, client, mock_churn_service):
        resp = client.post("/api/v1/customers/churn-predict-batch", json={"customer_ids": []})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False

    def test_oversized_batch_rejected(self, client, mock_churn_service):
        resp = client.post(
            "/api/v1/customers/churn-predict-batch",
            json={"customer_ids": list(range(1, 502))},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
