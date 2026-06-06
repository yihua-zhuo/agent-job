"""Unit tests for src/api/routers/customers.py — router endpoint tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.customers import customers_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException, ValidationException

# ---------------------------------------------------------------------------
# Helpers: build a minimal FastAPI app with overridden deps for each test
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _mock_to_dict(data: dict):
    """Build a lightweight object exposing a single to_dict() method.

    SimpleNamespace is deterministic and makes assertions on the rendered dict
    straightforward without the indirection of MagicMock attribute chains.
    """
    return SimpleNamespace(to_dict=lambda: data)


def _empty_enrichment_session():
    """Return a mock session whose ``execute`` resolves to a result with
    ``scalar_one_or_none() == None``.

    The GET customer endpoint runs a follow-up enrichment query directly on
    the session; an empty result is the common case (no enrichment record).
    """
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


CUSTOMER_ROW = {
    "id": 1,
    "tenant_id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "phone": "555",
    "company": "ACME",
    "status": "lead",
    "owner_id": 1,
    "tags": [],
    "created_at": None,
    "updated_at": None,
}


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with CustomerService fully mocked.

    ``CustomerService`` is monkey-patched to return a bare MagicMock so the
    real service never queries the session. The session itself is a minimal
    mock that returns no enrichment rows, which is what the GET customer
    endpoint's follow-up query expects.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    # Hoist the mock so the ``override_customer_service`` closure shares the
    # same instance across the test run; per-test attributes are then
    # configured in each test body.
    service_mock = MagicMock()
    _repo_sessions: list = []

    def override_customer_service(repository):
        return service_mock

    mock_session = _empty_enrichment_session()

    app = FastAPI()
    app.include_router(customers_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_session

    monkeypatch.setattr(
        "api.routers.customers.CustomerService",
        override_customer_service,
    )

    def make_mock_repo(session):
        _repo_sessions.append(session)
        return MagicMock(session=session)

    monkeypatch.setattr(
        "api.routers.customers.CustomerRepository",
        make_mock_repo,
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, service_mock, _repo_sessions


class TestCreateCustomerEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc, _ = client_with_service
        svc.create_customer = AsyncMock(return_value=_mock_to_dict({"name": "Alice"}))
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "alice@example.com", "owner_id": 1},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Alice"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc, _ = client_with_service
        svc.create_customer = AsyncMock(side_effect=ValidationException("Invalid data"))
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_invalid_email_rejected_by_validator(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "not-an-email", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_empty_name_rejected(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "   ", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_invalid_status_rejected(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Bob", "status": "invalid", "owner_id": 1},
        )
        assert resp.status_code == 422


class TestListCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.list_customers = AsyncMock(return_value=([_mock_to_dict(CUSTOMER_ROW)], 1))
        resp = client.get("/api/v1/customers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_with_pagination_params(self, client_with_service):
        client, svc, _ = client_with_service
        svc.list_customers = AsyncMock(return_value=([_mock_to_dict(CUSTOMER_ROW)], 10))
        resp = client.get("/api/v1/customers?page=2&page_size=5")
        assert resp.status_code == 200
        assert resp.json()["data"]["page"] == 2

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.get("/api/v1/customers?page_size=101")
        assert resp.status_code == 422


class TestSearchCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[_mock_to_dict(CUSTOMER_ROW)])
        resp = client.get("/api/v1/customers/search?keyword=alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["keyword"] == "alice"
        assert len(body["data"]["items"]) == 1

    def test_empty_keyword(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        resp = client.get("/api/v1/customers/search")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_keyword_too_long_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.get(f"/api/v1/customers/search?keyword={'x' * 201}")
        assert resp.status_code == 422

    def test_sanitize_strips_html_from_keyword(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        client.get("/api/v1/customers/search?keyword=<script>alert(1)</script>")
        svc.search_customers.assert_called_once()
        call_args = svc.search_customers.call_args
        # The sanitized keyword should have HTML stripped (empty string —
        # _sanitize removes the entire <script>...</script> as a matched pair)
        assert call_args[0][0] == "", f"Expected empty string after HTML strip, got {call_args[0][0]!r}"

    def test_keyword_exactly_200_chars_accepted(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        resp = client.get(f"/api/v1/customers/search?keyword={'y' * 200}")
        assert resp.status_code == 200


class TestGetCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_customer = AsyncMock(return_value=_mock_to_dict(CUSTOMER_ROW))
        resp = client.get("/api/v1/customers/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.get("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestUpdateCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_customer = AsyncMock(return_value=_mock_to_dict({**CUSTOMER_ROW, "name": "Updated"}))
        resp = client.put("/api/v1/customers/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.delete_customer = AsyncMock(return_value=_mock_to_dict(CUSTOMER_ROW))
        resp = client.delete("/api/v1/customers/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.delete_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.delete("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestAddTagEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.add_tag = AsyncMock(return_value=_mock_to_dict({"id": 1, "tag": "vip"}))
        resp = client.post("/api/v1/customers/1/tags", json={"tag": "vip"})
        assert resp.status_code == 200
        assert resp.json()["data"]["tag"] == "vip"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.add_tag = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.post("/api/v1/customers/9999/tags", json={"tag": "vip"})
        assert resp.status_code == 404

    def test_empty_tag_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.post("/api/v1/customers/1/tags", json={"tag": ""})
        assert resp.status_code == 422


class TestRemoveTagEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.remove_tag = AsyncMock(return_value=_mock_to_dict({"id": 1, "tag": "vip"}))
        resp = client.delete("/api/v1/customers/1/tags/vip")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.remove_tag = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.delete("/api/v1/customers/9999/tags/vip")
        assert resp.status_code == 404


class TestChangeStatusEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.change_status = AsyncMock(return_value=_mock_to_dict({"id": 1, "status": "active"}))
        resp = client.put("/api/v1/customers/1/status", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_invalid_status_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/customers/1/status", json={"status": "lead"})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.change_status = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999/status", json={"status": "active"})
        assert resp.status_code == 404


class TestAssignOwnerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_owner = AsyncMock(return_value=_mock_to_dict({"id": 1, "owner_id": 5}))
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": 5})
        assert resp.status_code == 200
        assert resp.json()["data"]["owner_id"] == 5

    def test_negative_owner_id_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": -1})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_owner = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999/owner", json={"owner_id": 1})
        assert resp.status_code == 404


class TestBulkImportEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.bulk_import = AsyncMock(return_value=2)
        resp = client.post(
            "/api/v1/customers/import",
            json={"customers": [{"name": "A"}, {"name": "B"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["imported"] == 2

    def test_empty_customers_allowed(self, client_with_service):
        client, svc, _ = client_with_service
        svc.bulk_import = AsyncMock(return_value=0)
        resp = client.post("/api/v1/customers/import", json={"customers": []})
        assert resp.status_code == 200
