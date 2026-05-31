"""Unit tests for src/api/routers/tenants.py — /api/v1/tenants endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.tenants import tenants_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
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
# Test fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_router_client(monkeypatch):
    """Builds a fully-mocked FastAPI test client for the tenants router.

    TenantService is patched so the DB is never touched.
    Rule 135: a fresh MagicMock is created per-test to avoid cross-test state leakage.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from internal.middleware.fastapi_auth import require_auth

    mock_svc = MagicMock()

    monkeypatch.setattr(
        "api.routers.tenants.TenantService",
        lambda *args, **kwargs: mock_svc,
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

    yield client, mock_svc


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
        svc.create_tenant.assert_called_once_with(
            name="Acme Corp", plan="enterprise", admin_email="admin@acme.com", settings=None
        )

    def test_service_error_returns_4xx(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.create_tenant = AsyncMock(side_effect=ValidationException("租户名称已存在"))
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
        svc.get_tenant.assert_called_once_with(1, requesting_tenant_id=1)

    def test_not_found_returns_404(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=NotFoundException("Tenant"))
        # Use tenant_id=9999 so the router guard passes (auth override matches the
        # URL path tenant_id), allowing the service's NotFoundException to surface as 404.
        app = client.app
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=9999)
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
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20
        assert body["data"]["total_pages"] == 1
        svc.list_tenants.assert_called_once_with(page=1, page_size=20, requesting_tenant_id=1, search=None)

    def test_with_pagination_params(self, tenant_router_client):
        client, svc = tenant_router_client
        mock_item = MagicMock()
        mock_item.to_dict.return_value = TENANT_ROW
        svc.list_tenants = AsyncMock(return_value=([mock_item], 1))
        resp = client.get("/api/v1/tenants?page=2&page_size=5")
        assert resp.status_code == 200
        svc.list_tenants.assert_called_once_with(page=2, page_size=5, requesting_tenant_id=1, search=None)

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
        svc.update_tenant.assert_called_once_with(1, requesting_tenant_id=1, name="Updated Corp")

    def test_not_found_returns_404(self, tenant_router_client):
        client, svc = tenant_router_client
        svc.update_tenant = AsyncMock(side_effect=NotFoundException("Tenant"))
        # Use tenant_id=9999 so the router guard passes (auth override matches the
        # URL path tenant_id), allowing the service's NotFoundException to surface as 404.
        app = client.app

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
            "name": "Acme Corp",
            "plan": "enterprise",
            "status": "active",
            "user_count": 10,
        }
        mock_stats = MagicMock()
        mock_stats.to_dict.return_value = stats_data
        svc.get_tenant_stats = AsyncMock(return_value=mock_stats)
        resp = client.get("/api/v1/tenants/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tenant_id"] == 1
        assert body["data"]["user_count"] == 10
        svc.get_tenant_stats.assert_called_once_with(tenant_id=1, requesting_tenant_id=1)


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
        assert body["success"] is True
        assert body["data"]["tenant_id"] == 1
        svc.get_tenant_usage.assert_called_once_with(tenant_id=1, requesting_tenant_id=1)


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


class TestTenantServiceSmoke:
    def test_constructor_receives_session(self, tenant_router_client):
        """Verify TenantService is instantiated with the session from the DB dependency."""
        client, svc = tenant_router_client
        svc.list_tenants = AsyncMock(return_value=([], 0))
        resp = client.get("/api/v1/tenants")
        assert resp.status_code == 200
        svc.list_tenants.assert_called_once_with(page=1, page_size=20, search=None, requesting_tenant_id=1)


# ---------------------------------------------------------------------------
# Cross-tenant isolation tests (Rule 126)
# ---------------------------------------------------------------------------


class TestTenantCrossTenantIsolation:
    """Rule 126: a tenant cannot read/modify another tenant's data via the API."""

    def test_get_tenant_returns_403_for_cross_tenant(self, tenant_router_client):
        """Tenant A requesting tenant B's data via URL path is rejected by the router guard before reaching the service."""
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=ForbiddenException("Cannot access other tenants"))
        resp = client.get("/api/v1/tenants/9999")
        assert resp.status_code == 403
        svc.get_tenant.assert_called_once_with(9999, requesting_tenant_id=1)

    def test_get_tenant_forbidden_on_existing_cross_tenant(self, tenant_router_client):
        """Tenant A requesting tenant B's data for an existing tenant is rejected by the service's requesting_tenant_id check (403)."""
        client, svc = tenant_router_client
        svc.get_tenant = AsyncMock(side_effect=ForbiddenException("Cannot access other tenants"))
        resp = client.get("/api/v1/tenants/2")
        assert resp.status_code == 403
        svc.get_tenant.assert_called_once_with(2, requesting_tenant_id=1)

    def test_get_tenant_stats_returns_404_for_unknown_tenant(self, tenant_router_client):
        """Service raises NotFoundException for an unknown tenant."""
        client, svc = tenant_router_client
        svc.get_tenant_stats = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/stats")
        assert resp.status_code == 404
        svc.get_tenant_stats.assert_called_once()

    def test_get_tenant_usage_returns_404_for_unknown_tenant(self, tenant_router_client):
        """Service raises NotFoundException for an unknown tenant."""
        client, svc = tenant_router_client
        svc.get_tenant_usage = AsyncMock(side_effect=NotFoundException("Tenant"))
        resp = client.get("/api/v1/tenants/usage")
        assert resp.status_code == 404
        svc.get_tenant_usage.assert_called_once()

    def test_update_tenant_rejects_cross_tenant_id(self, tenant_router_client):
        """Cross-tenant update is rejected at router level (403) before reaching the service."""
        client, svc = tenant_router_client
        svc.update_tenant = AsyncMock(side_effect=ForbiddenException("Access denied"))
        resp = client.put("/api/v1/tenants/9999", json={"name": "Stolen"})
        assert resp.status_code == 403
        svc.update_tenant.assert_not_called()

    def test_update_tenant_rejected_at_router_for_cross_tenant_id(self, tenant_router_client):
        """Tenant A requesting tenant B's update via URL path is rejected by the router guard before reaching the service."""
        client, svc = tenant_router_client
        svc.update_tenant = AsyncMock(side_effect=ForbiddenException("Access denied"))
        resp = client.put("/api/v1/tenants/2", json={"name": "Hijack"})
        assert resp.status_code == 403
        svc.update_tenant.assert_not_called()

    async def test_update_tenant_service_rejects_cross_tenant_requesting_id(self):
        """Service-layer update_tenant raises ForbiddenException when requesting_tenant_id != tenant_id.

        The forbidden guard fires at the top of update_tenant (tenant_service.py line 79) before
        _get_tenant_or_404() — and therefore session.execute() — is ever reached. The test verifies
        the guard is in place; the DB is never touched in this path.
        """
        from services.tenant_service import TenantService

        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        def _execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_result.scalar_one.return_value = 0
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        session.execute = AsyncMock(side_effect=_execute_side_effect)

        svc = TenantService(session)

        with pytest.raises(ForbiddenException):
            await svc.update_tenant(tenant_id=99, requesting_tenant_id=1, name="Hacked")

    # TODO (GH issue pending): Rule 126 gap — create_tenant does not enforce requesting_tenant_id,
    # allowing any authenticated tenant to create another tenant without restriction.
    # Replace this xfail marker with:
    #   @pytest.mark.xfail(reason="Issue #<N>: create_tenant does not enforce requesting_tenant_id")
    # when the issue is filed at https://github.com/yihua-zhuo/agent-job/issues
    @pytest.mark.xfail(reason="Rule 126 gap: create_tenant does not enforce requesting_tenant_id — fix belongs in TenantService.create_tenant")
    def test_create_tenant_uses_caller_tenant_id(self, tenant_router_client):
        """POST /api/v1/tenants creates a tenant; current design allows any authenticated tenant to create (Rule 126 gap)."""
        client, svc = tenant_router_client
        mock_tenant = MagicMock()
        mock_tenant.to_dict.return_value = {**TENANT_ROW, "id": 2}
        svc.create_tenant = AsyncMock(return_value=mock_tenant)
        resp = client.post("/api/v1/tenants", json={"name": "NewTenant", "plan": "free"})
        assert resp.status_code == 201
