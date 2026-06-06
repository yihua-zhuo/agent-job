"""Unit tests for the /score endpoints mounted on the customers router.

Uses the real ``ScoreService`` wired to a composable mock session via
``make_mock_session`` / ``MockState``. Only the AI client (a dependency
injected via the constructor) is mocked; the service's DB interaction is
exercised end-to-end so the router is the only thing under test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import customers as customers_module
from api.routers.customers import customers_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from tests.unit.conftest import MockResult, MockRow, MockState, make_mock_session

CUSTOMER_ID = 1
TENANT_ID = 1


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _customer_handler(state: MockState):
    """Match ``SELECT ... FROM customers WHERE id = :id AND tenant_id = :tenant_id``.

    SQLAlchemy Core appends a numeric suffix to bound param names
    (e.g. id_1, tenant_id_1); accept either form for robustness.
    """

    def handler(sql_text, params):
        if "from customers" in sql_text and "where" in sql_text:
            requested_tenant = params.get("tenant_id", params.get("tenant_id_1"))
            requested_customer = params.get("id", params.get("id_1"))
            if requested_customer is None or requested_customer not in state.customers:
                return MockResult(rows=[])
            record = state.customers[requested_customer]
            if record.get("tenant_id") != requested_tenant:
                return MockResult(rows=[])
            return MockResult(rows=[MockRow(record.copy())])
        return None

    return handler


def _enrichment_handler(state: MockState):
    """Match the enrichment-status subquery used in list_customers and friends.

    The router mounts those endpoints alongside score routes; returning an
    empty result keeps the session inert for any incidental queries.
    """

    def handler(sql_text, params):
        if "from customer_enrichments" in sql_text:
            return MockResult(rows=[])
        return None

    return handler


def _seed_customer(state: MockState, score_factors: dict | None) -> None:
    state.customers[CUSTOMER_ID] = {
        "id": CUSTOMER_ID,
        "tenant_id": TENANT_ID,
        "score_factors": score_factors,
    }


def _register_global_handlers(app: FastAPI) -> None:
    """Register the same exception handlers used in src/main.py.

    Mirrors the production handler chain so tests exercise the same error
    envelope shape the API actually returns.
    """
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from pkg.errors.app_exceptions import AppException

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


def _build_app(
    state: MockState,
    monkeypatch: pytest.MonkeyPatch,
    *,
    override_auth: bool = True,
    ai_client: object | None = None,
) -> TestClient:
    """Build a TestClient with a real ScoreService and a composable mock session.

    The session is wired to the customer and enrichment handlers. The AI
    client is injected by monkey-patching the router's ``ScoreService`` so
    the constructor picks it up; the test can then control AI behavior
    while the real service runs the rest.
    """
    session = make_mock_session(
        handlers=[_customer_handler(state), _enrichment_handler(state)],
        state=state,
    )

    real_score_service = customers_module.ScoreService

    def _patched_score_service(sess):
        return real_score_service(sess, ai_client=ai_client)

    monkeypatch.setattr(customers_module, "ScoreService", _patched_score_service)

    app = FastAPI()
    app.include_router(customers_router)
    if override_auth:
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: session

    _register_global_handlers(app)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_state(monkeypatch):
    state = MockState()
    yield state, _build_app(state, monkeypatch)


class TestScoreEndpoints:
    def test_post_score_returns_data(self, client_with_state):
        state, client = client_with_state
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "score" in body["data"]
        assert "tier" in body["data"]
        assert "top_factors" in body["data"]
        assert "recommendations" in body["data"]
        assert "message" in body

    def test_post_score_default_skips_ai(self, monkeypatch):
        """Default ``include_ai=False`` must not invoke the AI client."""
        state = MockState()
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        ai_client = MagicMock()
        ai_client.analyze_factors = AsyncMock()
        client = _build_app(state, monkeypatch, ai_client=ai_client)
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 200
        ai_client.analyze_factors.assert_not_called()
        # ``similar_leads`` is omitted when AI is not called
        assert "similar_leads" not in resp.json()["data"]

    def test_post_score_with_ai_enriches(self, monkeypatch):
        """``include_ai=True`` invokes the AI client and surfaces similar_leads."""
        state = MockState()
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        ai_client = MagicMock()
        ai_client.analyze_factors = AsyncMock(
            return_value={
                "similar_leads": [{"id": 42, "score": 0.9, "name": "Lead A"}],
                "recommendations": ["Expand to segment B"],
            }
        )
        client = _build_app(state, monkeypatch, ai_client=ai_client)
        resp = client.post("/api/v1/customers/1/score?include_ai=true")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert "similar_leads" in body
        assert body["similar_leads"] == [{"id": 42, "score": 0.9, "name": "Lead A"}]
        assert "Expand to segment B" in body["recommendations"]
        ai_client.analyze_factors.assert_awaited_once()

    def test_get_score_returns_data_with_factors(self, client_with_state):
        state, client = client_with_state
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "score" in body["data"]
        assert "tier" in body["data"]
        assert body["data"]["tier"] in ("A", "B", "C", "D")

    def test_get_score_returns_404_when_no_score(self, client_with_state):
        state, client = client_with_state
        # No customer seeded — service must raise NotFoundException
        resp = client.get("/api/v1/customers/9999/score")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "Score" in body["message"]

    def test_get_score_returns_404_when_customer_has_no_factors(self, client_with_state):
        state, client = client_with_state
        _seed_customer(state, score_factors=None)
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 404

    def test_post_score_requires_auth(self, monkeypatch):
        state = MockState()
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        client = _build_app(state, monkeypatch, override_auth=False)
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    def test_get_score_requires_auth(self, monkeypatch):
        state = MockState()
        _seed_customer(
            state,
            {
                "engagement_level": 80,
                "deal_velocity": 75,
                "support_health": 70,
                "payment_history": 65,
                "product_adoption": 60,
            },
        )
        client = _build_app(state, monkeypatch, override_auth=False)
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
