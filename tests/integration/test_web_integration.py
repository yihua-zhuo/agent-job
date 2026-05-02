"""Web-layer integration tests — FastAPI router endpoints via httpx.

Tests the full HTTP stack: routing, request validation, auth middleware,
response serialization, and multi-tenant isolation at the web layer.

Run with:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_web_integration.py -v

Requires TEST_DATABASE_URL (or DATABASE_URL) pointing at a live Postgres instance.
"""
from __future__ import annotations

import uuid

import pytest

from models.response import ResponseStatus


pytestmark = pytest.mark.integration


# ──────────────────────────────────────────────────────────────────────────────────────
#  Health & docs endpoints
# ──────────────────────────────────────────────────────────────────────────────────────

class TestRootEndpoints:
    """Smoke-test the root and OpenAPI docs endpoints (no auth required)."""

    async def test_root_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    async def test_openapi_schema_available(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data


# ──────────────────────────────────────────────────────────────────────────────────────
#  Customer endpoints — /api/v1/customers
# ──────────────────────────────────────────────────────────────────────────────────────

class TestCustomerEndpoints:
    """Full customer CRUD and search at the web layer."""

    async def test_create_customer(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        resp = await api_client.post(
            "/api/v1/customers",
            json={
                "name": f"Acme Corp {suffix}",
                "email": f"acme-{suffix}@example.com",
                "phone": "+1-555-0100",
                "company": "Acme Industries",
            },
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == f"Acme Corp {suffix}"
        assert data["data"]["email"] == f"acme-{suffix}@example.com"
        assert data["data"]["tenant_id"] == tenant_id_web

    async def test_create_customer_validation_error(self, api_client: "AsyncClient"):
        # Missing required 'name' field
        resp = await api_client.post("/api/v1/customers", json={"email": "bad"})
        assert resp.status_code == 422  # FastAPI validation error

    async def test_get_customer(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        create_resp = await api_client.post(
            "/api/v1/customers",
            json={
                "name": f"Get Test {suffix}",
                "email": f"get-{suffix}@example.com",
            },
        )
        created_id = create_resp.json()["data"]["id"]

        resp = await api_client.get(f"/api/v1/customers/{created_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == created_id

    async def test_get_customer_not_found(self, api_client: "AsyncClient"):
        resp = await api_client.get("/api/v1/customers/999999999")
        assert resp.status_code == 404

    async def test_list_customers(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        # Create two customers
        for i in range(2):
            suffix = uuid.uuid4().hex[:6]
            await api_client.post(
                "/api/v1/customers",
                json={"name": f"List Test {suffix}", "email": f"list-{i}-{suffix}@example.com"},
            )

        resp = await api_client.get("/api/v1/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) >= 2

    async def test_update_customer(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        create_resp = await api_client.post(
            "/api/v1/customers",
            json={
                "name": f"Update Test {suffix}",
                "email": f"update-{suffix}@example.com",
            },
        )
        customer_id = create_resp.json()["data"]["id"]

        resp = await api_client.patch(
            f"/api/v1/customers/{customer_id}",
            json={"name": "Updated Name", "status": "customer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"

    async def test_delete_customer(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        create_resp = await api_client.post(
            "/api/v1/customers",
            json={"name": f"Delete Test {suffix}", "email": f"del-{suffix}@example.com"},
        )
        customer_id = create_resp.json()["data"]["id"]

        resp = await api_client.delete(f"/api/v1/customers/{customer_id}")
        assert resp.status_code == 200

        # Verify it's gone
        get_resp = await api_client.get(f"/api/v1/customers/{customer_id}")
        assert get_resp.status_code == 404

    async def test_customer_cross_tenant_isolation(
        self,
        api_client: "AsyncClient",
        api_client_tenant_2: "AsyncClient",
        tenant_id_web: int,
        tenant_id_2_web: int,
    ):
        """Customer created by tenant 1 is invisible to tenant 2."""
        suffix = uuid.uuid4().hex[:6]
        resp1 = await api_client.post(
            "/api/v1/customers",
            json={"name": f"Tenant 1 Customer {suffix}", "email": f"t1-{suffix}@example.com"},
        )
        t1_id = resp1.json()["data"]["id"]

        # Tenant 2 should not see it
        list_resp = await api_client_tenant_2.get("/api/v1/customers")
        t2_ids = [c["id"] for c in list_resp.json()["data"]["items"]]
        assert t1_id not in t2_ids

        # Tenant 2 should get 404 on direct fetch
        detail_resp = await api_client_tenant_2.get(f"/api/v1/customers/{t1_id}")
        assert detail_resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────────────
#  User / auth endpoints — /api/v1/users
# ──────────────────────────────────────────────────────────────────────────────────────

class TestUserEndpoints:
    """User registration, login, and profile at the web layer."""

    async def test_register_user(self, api_client: "AsyncClient", tenant_id_web: int):
        suffix = uuid.uuid4().hex[:6]
        resp = await api_client.post(
            "/api/v1/users/register",
            json={
                "username": f"newuser_{suffix}",
                "email": f"new_{suffix}@example.com",
                "password": "Test@Pass1234",
                "full_name": "New User",
            },
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["username"] == f"newuser_{suffix}"

    async def test_register_user_duplicate_email(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "username": f"dupuser_{suffix}",
            "email": f"dup_{suffix}@example.com",
            "password": "Test@Pass1234",
        }
        resp1 = await api_client.post("/api/v1/users/register", json=payload)
        assert resp1.status_code == 200

        # Same email again
        resp2 = await api_client.post(
            "/api/v1/users/register",
            json={**payload, "username": f"another_{suffix}"},
        )
        assert resp2.status_code in (400, 409)

    async def test_login_user(self, api_client: "AsyncClient", tenant_id_web: int):
        suffix = uuid.uuid4().hex[:6]
        # Register first
        await api_client.post(
            "/api/v1/users/register",
            json={
                "username": f"loginuser_{suffix}",
                "email": f"login_{suffix}@example.com",
                "password": "Test@Pass1234",
            },
        )

        # Now login
        resp = await api_client.post(
            "/api/v1/users/login",
            json={
                "username": f"loginuser_{suffix}",
                "password": "Test@Pass1234",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "token" in data["data"]

    async def test_login_wrong_password(self, api_client: "AsyncClient", tenant_id_web: int):
        suffix = uuid.uuid4().hex[:6]
        # Register first
        await api_client.post(
            "/api/v1/users/register",
            json={
                "username": f"wronguser_{suffix}",
                "email": f"wrong_{suffix}@example.com",
                "password": "Test@Pass1234",
            },
        )

        resp = await api_client.post(
            "/api/v1/users/login",
            json={
                "username": f"wronguser_{suffix}",
                "password": "WrongPassword!",
            },
        )
        # Auth failure should return 401 or 400
        assert resp.status_code in (401, 400)

    async def test_get_current_user(self, api_client: "AsyncClient"):
        resp = await api_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "username" in data["data"]


# ──────────────────────────────────────────────────────────────────────────────────────
#  Ticket endpoints — /api/v1/tickets
# ──────────────────────────────────────────────────────────────────────────────────────

class TestTicketEndpoints:
    """Ticket CRUD at the web layer."""

    async def test_create_ticket(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        resp = await api_client.post(
            "/api/v1/tickets",
            json={
                "title": f"Bug Report {suffix}",
                "description": "Something is broken",
                "priority": "high",
                "channel": "email",
            },
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == f"Bug Report {suffix}"

    async def test_list_tickets(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        await api_client.post(
            "/api/v1/tickets",
            json={"title": f"Ticket List Test {suffix}", "description": "desc"},
        )

        resp = await api_client.get("/api/v1/tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_get_ticket_not_found(self, api_client: "AsyncClient"):
        resp = await api_client.get("/api/v1/tickets/999999999")
        assert resp.status_code == 404

    async def test_update_ticket(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        create_resp = await api_client.post(
            "/api/v1/tickets",
            json={"title": f"Original Title {suffix}", "description": "original"},
        )
        ticket_id = create_resp.json()["data"]["id"]

        resp = await api_client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "closed"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Pipeline / Sales endpoints — /api/v1/sales
# ──────────────────────────────────────────────────────────────────────────────────────

class TestSalesEndpoints:
    """Pipeline and opportunity endpoints at the web layer."""

    async def test_create_pipeline(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        resp = await api_client.post(
            "/api/v1/sales/pipelines",
            json={
                "name": f"Pipeline {suffix}",
                "description": "Main sales pipeline",
            },
        )
        assert resp.status_code == 200, f"Body: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == f"Pipeline {suffix}"

    async def test_list_pipelines(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        resp = await api_client.get("/api/v1/sales/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_get_pipeline_not_found(self, api_client: "AsyncClient"):
        resp = await api_client.get("/api/v1/sales/pipelines/999999999")
        assert resp.status_code == 404

    async def test_create_opportunity(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        # Need a pipeline first
        pipe_resp = await api_client.post(
            "/api/v1/sales/pipelines",
            json={"name": f"Opp Pipeline {suffix}"},
        )
        pipeline_id = pipe_resp.json()["data"]["id"]

        resp = await api_client.post(
            "/api/v1/sales/opportunities",
            json={
                "title": f"Deal {suffix}",
                "pipeline_id": pipeline_id,
                "stage": "prospecting",
                "amount": 50000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == f"Deal {suffix}"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Tenant endpoints — /api/v1/tenants
# ──────────────────────────────────────────────────────────────────────────────────────

class TestTenantEndpoints:
    """Tenant info and management at the web layer."""

    async def test_get_tenant_info(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        resp = await api_client.get("/api/v1/tenants/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] == tenant_id_web

    async def test_list_tenant_users(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        resp = await api_client.get("/api/v1/tenants/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ──────────────────────────────────────────────────────────────────────────────────────
#  Activity endpoints — /api/v1/activities
# ──────────────────────────────────────────────────────────────────────────────────────

class TestActivityEndpoints:
    """Activity log endpoints at the web layer."""

    async def test_list_activities(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        resp = await api_client.get("/api/v1/activities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_create_activity(
        self, api_client: "AsyncClient", tenant_id_web: int
    ):
        suffix = uuid.uuid4().hex[:6]
        resp = await api_client.post(
            "/api/v1/activities",
            json={
                "type": "call",
                "subject": f"Call {suffix}",
                "description": "Discussed the project",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ──────────────────────────────────────────────────────────────────────────────────────
#  Auth middleware — unauthenticated requests
# ──────────────────────────────────────────────────────────────────────────────────────

class TestAuthMiddleware:
    """Auth guard: endpoints that require Bearer token."""

    async def test_unauthenticated_request_returns_401(self, client):
        resp = await client.get("/api/v1/customers")
        assert resp.status_code == 401

    async def test_malformed_token_returns_401(self, client):
        resp = await client.get(
            "/api/v1/customers",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    async def test_valid_token_succeeds(self, api_client: "AsyncClient"):
        resp = await api_client.get("/api/v1/customers")
        # Should not be 401 — might be 200 or something else
        assert resp.status_code != 401