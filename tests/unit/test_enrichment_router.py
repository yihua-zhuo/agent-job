"""Unit tests for src/api/routers/enrichment.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.enrichment import enrichment_router
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db
from pkg.errors.app_exceptions import AppException, ValidationException
from tests.unit.conftest import make_mock_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


@pytest.fixture
def mock_db_session():
    # Router delegates to service; no DB queries needed in this fixture.
    return make_mock_session(handlers=[])


@pytest.fixture
def client_with_service(monkeypatch, mock_db_session):
    """Return a TestClient with EnrichmentService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth
    from services.enrichment_service import EnrichmentService

    mock_service = MagicMock()

    monkeypatch.setattr(
        "api.routers.enrichment.EnrichmentService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(enrichment_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_db_session

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/enrichment/lookup
# ---------------------------------------------------------------------------

class TestLookupEndpoint:
    def test_returns_enriched_data_on_success(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(
            return_value={
                "name": "Stripe",
                "domain": "stripe.com",
                "geo_city": "San Francisco",
                "metrics_employees": 8000,
            }
        )

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Stripe"
        assert body["data"]["domain"] == "stripe.com"

    def test_uses_company_name(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value={"name": "Acme Corp", "domain": "acme.com"})

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "company_name": "Acme Corp"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_validation_exception_returns_422(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(side_effect=ValidationException("service-level validation"))

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert "service-level validation" in body["message"]

    def test_model_validator_rejects_both_fields(self, client_with_service):
        client, _svc = client_with_service
        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com", "company_name": "Stripe"})
        assert resp.status_code == 422
        body = resp.json()
        assert "Provide exactly one of domain or company_name" in body["detail"][0]["msg"]

    def test_missing_customer_id_raises_422(self, client_with_service):
        """When customer_id is absent from the request body FastAPI returns 422."""
        client, _svc = client_with_service
        resp = client.post("/api/v1/enrichment/lookup", json={"domain": "stripe.com"})
        assert resp.status_code == 422

    def test_clearbit_api_error_returns_422(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(side_effect=ValidationException("Clearbit API error: 404"))

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "notfound.com"})
        assert resp.status_code == 422
        body = resp.json()
        assert "Clearbit API error" in body["message"]

    def test_passes_domain_to_service(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value={"name": "Stripe"})

        client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        svc.lookup.assert_awaited_once_with(domain="stripe.com", company_name=None, tenant_id=1, customer_id=42)

    def test_passes_company_name_to_service(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value={"name": "Acme Corp"})

        client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "company_name": "Acme Corp"})
        svc.lookup.assert_awaited_once_with(domain=None, company_name="Acme Corp", tenant_id=1, customer_id=42)

    def test_success_response_has_envelope_shape(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value={"name": "Stripe", "domain": "stripe.com"})

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        body = resp.json()
        assert "success" in body
        assert "data" in body
        assert "message" in body
