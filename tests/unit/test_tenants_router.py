"""Unit tests for src/api/routers/tenants.py — /api/v1/tenants endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from api.routers.tenants import (
    tenants_router,
    _http_status,
)
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_service_response(status=ResponseStatus.SUCCESS, data=None, message="OK"):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    resp.message = message
    return resp


TENANT_ROW = {
    "id": 1,
    "name": "Acme Corp",
    "plan": "enterprise",
    "status": "active",
    "settings": {},
    "created_at": None,
    "updated_at": None,
}


# ---------------------------------------------------------------------------
# _http_status
# ---------------------------------------------------------------------------

class TestHttpStatus:
    def test_success_returns_200(self):
        assert _http_status(ResponseStatus.SUCCESS) == 200

    def test_not_found_returns_404(self):
        assert _http_status(ResponseStatus.NOT_FOUND) == 404

    def test_validation_error_returns_400(self):
        assert _http_status(ResponseStatus.VALIDATION_ERROR) == 400

    def test_unauthorized_returns_401(self):
        assert _http_status(ResponseStatus.UNAUTHORIZED) == 401

    def test_server_error_returns_500(self):
        assert _http_status(ResponseStatus.SERVER_ERROR) == 500

    def test_error_returns_400(self):
        assert _http_status(ResponseStatus.ERROR) == 400

    def test_unknown_status_returns_400(self):
        unknown = MagicMock()
        assert _http_status(unknown) == 400


# ---------------------------------------------------------------------------
# Mock list object for service responses
# ---------------------------------------------------------------------------

class MockTenantList:
    """List-like mock with dict-like subscript access.

    Required because router handlers access resp.data["items"], resp.data["total"], etc.
    via subscript [] on the data object returned from the service.
    """
    def __init__(self, items):
        self.items = items
        self.total = len(items)
        self.page = 1
        self.page_size = 20

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.tenants.TenantService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(tenants_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(exc)},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/tenants — create tenant
# ---------------------------------------------------------------------------

class TestCreateTenantEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_tenant = AsyncMock(
            return_value=_make_service_response(data=TENANT_ROW, message="租户创建成功")
        )
        resp = client.post(
            "/api/v1/tenants",
            json={
                "name": "Acme Corp",
                "plan": "enterprise",
                "admin_email": "admin@acme.com",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Acme Corp"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_tenant = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="租户名称已存在",
            )
        )
        resp = client.post(
            "/api/v1/tenants",
            json={
                "name": "Acme Corp",
                "plan": "enterprise",
            },
        )
        assert resp.status_code == 400

    def test_empty_name_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "", "plan": "basic"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/{tenant_id} — get tenant
# ---------------------------------------------------------------------------

class TestGetTenantEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.get_tenant = AsyncMock(
            return_value=_make_service_response(data=TENANT_ROW)
        )
        resp = client.get("/api/v1/tenants/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_tenant = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="租户不存在"
            )
        )
        resp = client.get("/api/v1/tenants/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tenants — list tenants
# ---------------------------------------------------------------------------

class TestListTenantsEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_list = MockTenantList([TENANT_ROW])
        svc.list_tenants = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.get("/api/v1/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1

    def test_with_pagination_params(self, client_with_service):
        client, svc = client_with_service
        mock_list = MockTenantList([TENANT_ROW])
        mock_list.page = 2
        mock_list.page_size = 5
        svc.list_tenants = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.get("/api/v1/tenants?page=2&page_size=5")
        assert resp.status_code == 200

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/tenants?page_size=101")
        assert resp.status_code == 422

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.list_tenants = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/tenants")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /api/v1/tenants/{tenant_id} — update tenant
# ---------------------------------------------------------------------------

class TestUpdateTenantEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated = {**TENANT_ROW, "name": "Updated Corp"}
        svc.update_tenant = AsyncMock(
            return_value=_make_service_response(data=updated, message="租户更新成功")
        )
        resp = client.put("/api/v1/tenants/1", json={"name": "Updated Corp"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Corp"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_tenant = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="租户不存在"
            )
        )
        resp = client.put("/api/v1/tenants/9999", json={"name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/tenants/{tenant_id} — delete tenant
# ---------------------------------------------------------------------------

class TestDeleteTenantEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_tenant = AsyncMock(
            return_value=_make_service_response(message="租户删除成功")
        )
        resp = client.delete("/api/v1/tenants/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_tenant = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="租户不存在"
            )
        )
        resp = client.delete("/api/v1/tenants/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/{tenant_id}/stats — tenant stats
# ---------------------------------------------------------------------------

class TestTenantStatsEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        stats_data = {
            "tenant_id": 1,
            "user_count": 10,
            "storage_used": 1024,
            "api_calls": 5000,
        }
        svc.get_tenant_stats = AsyncMock(
            return_value=_make_service_response(data=stats_data)
        )
        resp = client.get("/api/v1/tenants/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tenant_id"] == 1
        assert body["data"]["user_count"] == 10

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_tenant_stats = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="租户不存在"
            )
        )
        resp = client.get("/api/v1/tenants/9999/stats")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/{tenant_id}/usage — tenant usage
# ---------------------------------------------------------------------------

class TestTenantUsageEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        usage_data = {
            "tenant_id": 1,
            "user_count": 5,
            "storage_used": 512,
            "api_calls": 2500,
        }
        svc.get_tenant_usage = AsyncMock(
            return_value=_make_service_response(data=usage_data)
        )
        resp = client.get("/api/v1/tenants/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["api_calls"] == 2500

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_tenant_usage = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="租户不存在"
            )
        )
        resp = client.get("/api/v1/tenants/9999/usage")
        assert resp.status_code == 404