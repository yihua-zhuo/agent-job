"""Unit tests for src/api/routers/enrichment.py."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.enrichment import enrichment_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import AppException, NotFoundException, ValidationException
from tests.unit.conftest import MockState, make_customer_handler, make_mock_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


@pytest.fixture
def mock_db_session():
    # Include a customer handler so router's tenant pre-check passes.
    state = MockState()
    state.customers[42] = {"id": 42, "tenant_id": 1, "name": "Test Customer"}
    state.customers[99] = {"id": 99, "tenant_id": 1, "name": "Another Customer"}
    return make_mock_session([make_customer_handler(state)], state=state)


@pytest.fixture
def client_with_service_as_tenant_2(monkeypatch, mock_db_session):
    """Return a TestClient authenticated as tenant_id=2."""
    from internal.middleware.fastapi_auth import require_auth

    mock_service = AsyncMock()

    monkeypatch.setattr(
        "api.routers.enrichment.EnrichmentService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(enrichment_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=2)
    app.dependency_overrides[get_db] = lambda: mock_db_session

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, list) and detail:
            msg = detail[0].get("msg", str(detail))
        else:
            msg = str(detail)
        return JSONResponse(
            status_code=422,
            content={"success": False, "message": msg, "detail": detail},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


@pytest.fixture
def client_with_service(monkeypatch, mock_db_session):
    """Return a TestClient with EnrichmentService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth

    mock_service = AsyncMock()

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

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, list) and detail:
            msg = detail[0].get("msg", str(detail))
        else:
            msg = str(detail)
        return JSONResponse(
            status_code=422,
            content={"success": False, "message": msg, "detail": detail},
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
            return_value=(
                {
                    "name": "Stripe",
                    "domain": "stripe.com",
                    "geo_city": "San Francisco",
                    "metrics_employees": 8000,
                },
                {"name": "Stripe", "domain": "stripe.com"},  # raw_data
            )
        )

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Stripe"
        assert body["data"]["domain"] == "stripe.com"

    def test_uses_company_name(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value=({"name": "Acme Corp", "domain": "acme.com"}, {"name": "Acme Corp"}))

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
        resp = client.post(
            "/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com", "company_name": "Stripe"}
        )
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
        svc.lookup = AsyncMock(return_value=({"name": "Stripe"}, {}))

        client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        svc.lookup.assert_awaited_once_with(domain="stripe.com", company_name=None, tenant_id=1, customer_id=42)

    def test_passes_company_name_to_service(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value=({"name": "Acme Corp"}, {}))

        client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "company_name": "Acme Corp"})
        svc.lookup.assert_awaited_once_with(domain=None, company_name="Acme Corp", tenant_id=1, customer_id=42)

    def test_success_response_has_envelope_shape(self, client_with_service):
        client, svc = client_with_service
        svc.lookup = AsyncMock(return_value=({"name": "Stripe", "domain": "stripe.com"}, {}))

        resp = client.post("/api/v1/enrichment/lookup", json={"customer_id": 42, "domain": "stripe.com"})
        body = resp.json()
        assert "success" in body
        assert "data" in body
        assert "message" in body
        assert isinstance(body["message"], str)


class TestRefreshEndpoint:
    """Unit tests for POST /api/v1/enrichment/refresh/{customer_id}."""

    def test_refresh_returns_enriched_data(self, client_with_service):
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(
            return_value=(
                {
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "geo_city": "New York",
                },
                None,  # upserted record
            )
        )

        resp = client.post("/api/v1/enrichment/refresh/42", json={"domain": "acme.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Acme Corp"
        assert body["data"]["domain"] == "acme.com"

    def test_refresh_passes_correct_args(self, client_with_service):
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(return_value=({"name": "Acme Corp"}, None))

        resp = client.post(
            "/api/v1/enrichment/refresh/99",
            json={"domain": "acme.com"},
        )
        assert resp.status_code == 200
        svc.refresh_full.assert_awaited_once_with(
            customer_id=99,
            tenant_id=1,
            domain_override="acme.com",
            company_name_override=None,
        )

    def test_refresh_passes_domain(self, client_with_service):
        """Refresh with a domain body passes domain and company_name to the service."""
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(return_value=({"name": "Acme Corp"}, None))

        resp = client.post("/api/v1/enrichment/refresh/7", json={"domain": "example.com"})
        assert resp.status_code == 200
        svc.refresh_full.assert_awaited_once_with(
            customer_id=7,
            tenant_id=1,
            domain_override="example.com",
            company_name_override=None,
        )

    def test_refresh_no_body_no_prior_enrichment_returns_422(self, client_with_service):
        """When no body and no prior enrichment record, service raises ValidationException."""
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(side_effect=ValidationException("domain or company_name is required when customer has no prior enrichment record"))

        resp = client.post("/api/v1/enrichment/refresh/7")
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert "domain or company_name is required" in body["message"]

    def test_refresh_cross_tenant_returns_404(self, client_with_service_as_tenant_2):
        """A tenant cannot refresh another tenant's customer's enrichment.

        This is a router-level isolation test: the service is mocked to raise
        NotFoundException immediately, short-circuiting before any DB access.
        It verifies that the router correctly propagates the 404 response from
        the service; it does not exercise cross-tenant database-level filtering.
        """
        client, svc = client_with_service_as_tenant_2
        svc.refresh_full = AsyncMock(side_effect=NotFoundException("Customer"))

        resp = client.post("/api/v1/enrichment/refresh/42", json={"domain": "acme.com"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["code"] == "NOT_FOUND"
        svc.refresh_full.assert_awaited_once_with(customer_id=42, tenant_id=2, domain_override="acme.com", company_name_override=None)

    def test_refresh_customer_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(side_effect=NotFoundException("Customer"))

        resp = client.post("/api/v1/enrichment/refresh/9999", json={"domain": "acme.com"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "not found" in body["message"]
        assert body["code"] == "NOT_FOUND"

    def test_refresh_validation_error_returns_422(self, client_with_service):
        client, svc = client_with_service
        svc.refresh_full = AsyncMock(side_effect=ValidationException("No company found for the given domain"))

        resp = client.post("/api/v1/enrichment/refresh/42", json={"domain": "notfound.com"})
        assert resp.status_code == 422
        body = resp.json()
        assert "No company found" in body["message"]
        assert body["code"] == "VALIDATION_ERROR"

    def test_refresh_rejects_both_fields(self, client_with_service):
        """When neither domain nor company_name is provided, the model validator raises."""
        from pydantic import ValidationError as PydanticValidationError

        from models.enrichment import EnrichmentRefreshRequest

        with pytest.raises(PydanticValidationError) as exc_info:
            EnrichmentRefreshRequest.model_validate({})
        errors = exc_info.value.errors()
        assert any("At least one of domain or company_name is required" in str(e.get("msg", "")) for e in errors)

    def test_refresh_accepts_both_fields(self, client_with_service):
        """When both domain and company_name are provided, the model accepts the request.

        The service will use domain and ignore company_name (domain takes priority).
        """
        from pydantic import ValidationError as PydanticValidationError

        from models.enrichment import EnrichmentRefreshRequest

        # Both present → valid (at-least-one constraint satisfied)
        try:
            req = EnrichmentRefreshRequest.model_validate({"domain": "x.com", "company_name": "X Corp"})
        except PydanticValidationError:
            pytest.fail("ValidationError should not be raised when both fields are provided")
        assert req.domain == "x.com"
        assert req.company_name == "X Corp"
