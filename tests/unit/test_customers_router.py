"""Unit tests for src/api/routers/customers.py — typed response schemas and _http_status."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from api.routers.customers import (
    customers_router,
    _http_status,
    _sanitize,
    _is_valid_email,
)
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers: build a minimal FastAPI app with overridden deps for each test
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_app(service_mock) -> tuple[FastAPI, TestClient]:
    """Create a test FastAPI app that injects service_mock responses."""
    from internal.middleware.fastapi_auth import require_auth

    app = FastAPI()
    app.include_router(customers_router)

    # Override auth
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    # Override DB session
    app.dependency_overrides[get_db] = lambda: MagicMock()

    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# _http_status
# ---------------------------------------------------------------------------

class TestHttpStatus:
    def test_success_returns_200(self):
        assert _http_status(ResponseStatus.SUCCESS) == 200

    def test_warning_returns_200(self):
        assert _http_status(ResponseStatus.WARNING) == 200

    def test_not_found_returns_404(self):
        assert _http_status(ResponseStatus.NOT_FOUND) == 404

    def test_validation_error_returns_400(self):
        assert _http_status(ResponseStatus.VALIDATION_ERROR) == 400

    def test_unauthorized_returns_401(self):
        assert _http_status(ResponseStatus.UNAUTHORIZED) == 401

    def test_forbidden_returns_403(self):
        assert _http_status(ResponseStatus.FORBIDDEN) == 403

    def test_server_error_returns_500(self):
        assert _http_status(ResponseStatus.SERVER_ERROR) == 500

    def test_error_returns_400(self):
        assert _http_status(ResponseStatus.ERROR) == 400

    def test_unknown_status_returns_400(self):
        # Test fallback: pass a value not in the mapping
        unknown = MagicMock()
        assert _http_status(unknown) == 400


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------

class TestSanitize:
    def test_strips_html_tags(self):
        assert _sanitize("<b>hello</b>") == "hello"

    def test_strips_nested_tags(self):
        assert _sanitize("<script>alert(1)</script>text") == "text"

    def test_removes_control_chars(self):
        result = _sanitize("hello\x00world")
        assert "\x00" not in result

    def test_strips_whitespace(self):
        assert _sanitize("  hello  ") == "hello"

    def test_empty_string_passthrough(self):
        assert _sanitize("") == ""

    def test_none_passthrough(self):
        assert _sanitize(None) is None

    def test_normal_string_unchanged(self):
        assert _sanitize("john doe") == "john doe"


# ---------------------------------------------------------------------------
# _is_valid_email
# ---------------------------------------------------------------------------

class TestIsValidEmail:
    def test_valid_email(self):
        assert _is_valid_email("user@example.com") is True

    def test_valid_email_with_plus(self):
        assert _is_valid_email("user+tag@domain.co.uk") is True

    def test_missing_at_sign(self):
        assert _is_valid_email("userexample.com") is False

    def test_missing_domain(self):
        assert _is_valid_email("user@") is False

    def test_invalid_tld_too_short(self):
        assert _is_valid_email("user@domain.c") is False

    def test_empty_string(self):
        assert _is_valid_email("") is False


# ---------------------------------------------------------------------------
# Router endpoint tests using TestClient with mocked CustomerService
# ---------------------------------------------------------------------------

def _make_service_response(status=ResponseStatus.SUCCESS, data=None, message="OK"):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    resp.message = message
    return resp


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

LIST_DATA = {
    "items": [CUSTOMER_ROW],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "has_next": False,
    "has_prev": False,
}


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with CustomerService fully mocked."""
    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()

    # Patch CustomerService constructor to return our mock
    monkeypatch.setattr(
        "api.routers.customers.CustomerService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(customers_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


class TestCreateCustomerEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_customer = AsyncMock(
            return_value=_make_service_response(data=CUSTOMER_ROW, message="客户创建成功")
        )
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "alice@example.com", "owner_id": 1},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Alice"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_customer = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="Invalid data",
            )
        )
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "owner_id": 1},
        )
        assert resp.status_code == 400

    def test_invalid_email_rejected_by_validator(self, client_with_service):
        client, svc = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "not-an-email", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_empty_name_rejected(self, client_with_service):
        client, svc = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "   ", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_invalid_status_rejected(self, client_with_service):
        client, svc = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Bob", "status": "invalid", "owner_id": 1},
        )
        assert resp.status_code == 422


class TestListCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.list_customers = AsyncMock(
            return_value=_make_service_response(data=LIST_DATA, message="OK")
        )
        resp = client.get("/api/v1/customers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_with_pagination_params(self, client_with_service):
        client, svc = client_with_service
        paginated = {**LIST_DATA, "page": 2, "page_size": 5, "total": 10, "total_pages": 2, "has_prev": True}
        svc.list_customers = AsyncMock(
            return_value=_make_service_response(data=paginated)
        )
        resp = client.get("/api/v1/customers?page=2&page_size=5")
        assert resp.status_code == 200
        assert resp.json()["data"]["page"] == 2

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/customers?page_size=101")
        assert resp.status_code == 422

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.list_customers = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.UNAUTHORIZED, message="Unauthorized"
            )
        )
        resp = client.get("/api/v1/customers")
        assert resp.status_code == 401


class TestSearchCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.search_customers = AsyncMock(
            return_value=_make_service_response(
                data={"keyword": "alice", "items": [CUSTOMER_ROW]},
                message="",
            )
        )
        resp = client.get("/api/v1/customers/search?keyword=alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["keyword"] == "alice"
        assert len(body["data"]["items"]) == 1

    def test_empty_keyword(self, client_with_service):
        client, svc = client_with_service
        svc.search_customers = AsyncMock(
            return_value=_make_service_response(
                data={"keyword": "", "items": []},
                message="",
            )
        )
        resp = client.get("/api/v1/customers/search")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_keyword_too_long_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get(f"/api/v1/customers/search?keyword={'x' * 201}")
        assert resp.status_code == 422


class TestGetCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.get_customer = AsyncMock(
            return_value=_make_service_response(data=CUSTOMER_ROW, message="OK")
        )
        resp = client.get("/api/v1/customers/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_customer = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.get("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestUpdateCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.update_customer = AsyncMock(
            return_value=_make_service_response(
                data={**CUSTOMER_ROW, "name": "Updated"}, message="客户更新成功"
            )
        )
        resp = client.put("/api/v1/customers/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_customer = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.put("/api/v1/customers/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_customer = AsyncMock(
            return_value=_make_service_response(message="客户删除成功")
        )
        resp = client.delete("/api/v1/customers/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] is None

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_customer = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.delete("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestAddTagEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.add_tag = AsyncMock(
            return_value=_make_service_response(
                data={"id": 1, "tag": "vip"}, message="Tag added"
            )
        )
        resp = client.post("/api/v1/customers/1/tags", json={"tag": "vip"})
        assert resp.status_code == 200
        assert resp.json()["data"]["tag"] == "vip"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.add_tag = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.post("/api/v1/customers/9999/tags", json={"tag": "vip"})
        assert resp.status_code == 404

    def test_empty_tag_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post("/api/v1/customers/1/tags", json={"tag": ""})
        assert resp.status_code == 422


class TestRemoveTagEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.remove_tag = AsyncMock(
            return_value=_make_service_response(
                data={"id": 1, "tag": "vip"}, message="Tag removed"
            )
        )
        resp = client.delete("/api/v1/customers/1/tags/vip")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.remove_tag = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.delete("/api/v1/customers/9999/tags/vip")
        assert resp.status_code == 404


class TestChangeStatusEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.change_status = AsyncMock(
            return_value=_make_service_response(
                data={"id": 1, "status": "active"}, message="Status changed"
            )
        )
        resp = client.put("/api/v1/customers/1/status", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_invalid_status_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.put("/api/v1/customers/1/status", json={"status": "lead"})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.change_status = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.put("/api/v1/customers/9999/status", json={"status": "active"})
        assert resp.status_code == 404


class TestAssignOwnerEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.assign_owner = AsyncMock(
            return_value=_make_service_response(
                data={"id": 1, "owner_id": 5}, message="Owner assigned"
            )
        )
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": 5})
        assert resp.status_code == 200
        assert resp.json()["data"]["owner_id"] == 5

    def test_negative_owner_id_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": -1})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.assign_owner = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="客户不存在"
            )
        )
        resp = client.put("/api/v1/customers/9999/owner", json={"owner_id": 1})
        assert resp.status_code == 404


class TestBulkImportEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.bulk_import = AsyncMock(
            return_value=_make_service_response(
                data={"imported": 2, "errors": []}, message="Imported"
            )
        )
        resp = client.post(
            "/api/v1/customers/import",
            json={"customers": [{"name": "A"}, {"name": "B"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["imported"] == 2

    def test_empty_customers_allowed(self, client_with_service):
        client, svc = client_with_service
        svc.bulk_import = AsyncMock(
            return_value=_make_service_response(
                data={"imported": 0, "errors": []}, message="Imported"
            )
        )
        resp = client.post("/api/v1/customers/import", json={"customers": []})
        assert resp.status_code == 200

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.bulk_import = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.post(
            "/api/v1/customers/import",
            json={"customers": [{"name": "A"}]},
        )
        assert resp.status_code == 500