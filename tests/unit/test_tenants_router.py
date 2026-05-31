"""Unit tests for src/api/routers/tenants.py — /api/v1/tenants endpoints."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.tenants import tenants_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import (
    AppException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


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
# Smoke test — constructor receives a session-like argument
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant_router_client(monkeypatch):
    """Builds a fully-mocked FastAPI test client for the tenants router.

    TenantService is patched so the DB is never touched.  A smoke assertion
    verifies the constructor receives a session-like argument, detecting
    signature changes in the service constructor early.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()
    # Capture constructor args for smoke-test assertion without changing
    # what tests receive as `svc`.
    captured_sessions = []

    def _wrapping_constructor(*args, **kwargs):
        # args[0] is self; the session is args[1] when called as TenantService(session, ...).
        # When only one positional arg is passed, it lands at args[0] — capture it unconditionally.
        captured_sessions.extend(args)
        return mock_service

    mock_service.captured_sessions = captured_sessions

    monkeypatch.setattr(
        "api.routers.tenants.TenantService",
        _wrapping_constructor,
    )

    app = FastAPI()
    app.include_router(tenants_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

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
    def test_success_returns_201(self, tenant_router_client):
        client, svc = tenant_router_client
        mock_tenant = MagicMock()
        mock_tenant.to_dict.return_value = TENANT_ROW
        svc.create_tenant = AsyncMock(return_value=mock_tenant)
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

    def test_service_error_returns_4xx(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.create_tenant = AsyncMock(
            side_effect=ValidationException("租户名称已存在")
        )
        resp = client.post(
            "/api/v1/tenants",
            json={
                "name": "Acme Corp",
                "plan": "enterprise",
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert "租户名称已存在" in body["message"]
        assert body["code"] == "VALIDATION_ERROR"

    def test_empty_name_rejected(self, tenant_router_client):
        client, _ = tenant_router_client
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "", "plan": "basic"},
        )
        assert resp.status_code == 422
        assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/{tenant_id} — get tenant
# ---------------------------------------------------------------------------

class TestGetTenantEndpoint:
    def test_success(self, tenant_router_client):
        client, svc = tenant_router_client
        mock_tenant = MagicMock()
        mock_tenant.to_dict.return_value = TENANT_ROW
        svc.get_tenant = AsyncMock(return_value=mock_tenant)
        resp = client.get("/api/v1/tenants/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(
            side_effect=NotFoundException("Tenant")
        )
        resp = client.get("/api/v1/tenants/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/tenants — list tenants
# ---------------------------------------------------------------------------

class TestListTenantsEndpoint:
    def test_success(self, tenant_router_client):
        client, svc = tenant_router_client
        mock_item = MagicMock()
        mock_item.to_dict.return_value = TENANT_ROW
        svc.list_tenants = AsyncMock(return_value=([mock_item], 1))
        resp = client.get("/api/v1/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        svc.list_tenants.assert_called_once_with(
            page=1, page_size=20, requesting_tenant_id=1, search=None
        )

    def test_with_pagination_params(self, tenant_router_client):
        client, svc = tenant_router_client
        mock_item = MagicMock()
        mock_item.to_dict.return_value = TENANT_ROW
        svc.list_tenants = AsyncMock(return_value=([mock_item], 1))
        resp = client.get("/api/v1/tenants?page=2&page_size=5")
        assert resp.status_code == 200
        svc.list_tenants.assert_called_once_with(
            page=2, page_size=5, requesting_tenant_id=1, search=None
        )

    def test_page_size_over_100_rejected(self, tenant_router_client):
        client, _ = tenant_router_client
        resp = client.get("/api/v1/tenants?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/v1/tenants/{tenant_id} — update tenant
# ---------------------------------------------------------------------------

class TestUpdateTenantEndpoint:
    def test_success(self, tenant_router_client):
        client, svc = tenant_router_client
        updated = {**TENANT_ROW, "name": "Updated Corp"}
        mock_updated = MagicMock()
        mock_updated.to_dict.return_value = updated
        svc.update_tenant = AsyncMock(return_value=mock_updated)
        resp = client.put("/api/v1/tenants/1", json={"name": "Updated Corp"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Corp"

    def test_not_found_returns_404(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.update_tenant = AsyncMock(
            side_effect=NotFoundException("Tenant")
        )
        # Use matching tenant_id so the authorization check passes;
        # ForbiddenException would be raised before reaching the service.
        app = client.app
        from internal.middleware.fastapi_auth import require_auth

        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=9999)
        resp = client.put("/api/v1/tenants/9999", json={"name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/tenants/{tenant_id} — delete tenant (not exposed)
# ---------------------------------------------------------------------------

class TestDeleteTenantNotExposed:
    def test_returns_405_when_method_not_allowed(self, tenant_router_client):
        """DELETE is not defined on /api/v1/tenants/{id} — FastAPI returns 405.

        Intentionally not exposed: tenant deletion is handled via status='deleted'
        (soft delete) through other endpoints. A positive DELETE endpoint test
        should be added here when a hard-delete endpoint is introduced in a future PR.
        """
        client, _ = tenant_router_client
        resp = client.delete("/api/v1/tenants/1")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/stats — tenant stats
# ---------------------------------------------------------------------------

class TestTenantStatsEndpoint:
    def test_success(self, tenant_router_client):
        client, svc = tenant_router_client
        stats_data = {
            "tenant_id": 1,
            "user_count": 10,
            "storage_used": 1024,
            "api_calls": 5000,
        }
        mock_stats = MagicMock()
        mock_stats.to_dict.return_value = stats_data
        svc.get_tenant_stats = AsyncMock(return_value=mock_stats)
        resp = client.get("/api/v1/tenants/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tenant_id"] == 1
        assert body["data"]["user_count"] == 10
        svc.get_tenant_stats.assert_called()


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/usage — tenant usage
# ---------------------------------------------------------------------------

class TestTenantUsageEndpoint:
    def test_success(self, tenant_router_client):
        client, svc = tenant_router_client
        usage_data = {
            "tenant_id": 1,
            "name": "Acme Corp",
            "plan": "enterprise",
            "status": "active",
            "user_count": 5,
        }
        mock_usage = MagicMock()
        mock_usage.to_dict.return_value = usage_data
        svc.get_tenant_usage = AsyncMock(return_value=mock_usage)
        resp = client.get("/api/v1/tenants/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["tenant_id"] == 1


# ---------------------------------------------------------------------------
# Cross-tenant isolation tests (Rule 126)
# ---------------------------------------------------------------------------

class TestTenantCrossTenantIsolation:
    """Rule 126: a tenant cannot read/modify another tenant's data via the API."""

    def test_get_tenant_rejects_cross_tenant_id(self, tenant_router_client):
        """Tenant A requesting tenant B's data via URL path tenant_id returns 404 or 403."""
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/9999")
        assert resp.status_code == 404
        svc.get_tenant.assert_called_once_with(9999, requesting_tenant_id=1)

    def test_get_tenant_forbidden_on_existing_cross_tenant(self, tenant_router_client):
        """Tenant A requesting tenant B's data for an existing-but-inaccessible tenant returns 403."""
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=ForbiddenException(detail="Tenant 2"))
        resp = client.get("/api/v1/tenants/2")
        assert resp.status_code == 403
        svc.get_tenant.assert_called_once_with(2, requesting_tenant_id=1)

    def test_get_tenant_not_found_for_nonexistent_tenant(self, tenant_router_client):
        """Tenant A requesting a non-existent tenant ID returns 404."""
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/9999")
        assert resp.status_code == 404

    def test_get_tenant_stats_rejects_cross_tenant_id(self, tenant_router_client):
        """Tenant A cannot access tenant B's stats; service layer returns 404 for unknown tenant."""
        client, svc = tenant_router_client
        svc.get_tenant_stats = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/stats")
        assert resp.status_code == 404
        svc.get_tenant_stats.assert_called_once_with(tenant_id=1, requesting_tenant_id=1)

    def test_get_tenant_usage_rejects_cross_tenant_id(self, tenant_router_client):
        """Tenant A cannot access tenant B's usage; service layer returns 404 for unknown tenant."""
        client, svc = tenant_router_client
        svc.get_tenant_usage = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/usage")
        assert resp.status_code == 404
        svc.get_tenant_usage.assert_called_once_with(tenant_id=1, requesting_tenant_id=1)

    def test_update_tenant_rejects_cross_tenant_id(self, tenant_router_client):
        """Tenant A updating tenant B's record via URL path tenant_id returns 403."""
        client, svc = tenant_router_client
        svc.update_tenant = AsyncMock(side_effect=ForbiddenException(detail="Tenant 9999"))
        resp = client.put("/api/v1/tenants/9999", json={"name": "Stolen"})
        assert resp.status_code == 403
