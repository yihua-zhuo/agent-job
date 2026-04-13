"""
Integration tests using a real PostgreSQL database on Supabase.

Run with:  pytest tests/integration/ -v
All tests use async/await with the real DB via pytest-asyncio + async_session.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from src.services import (
    auth_service,
    customer_service,
    pipeline_service,
    sales_service,
    ticket_service,
    user_service,
)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Pipeline integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestPipelineIntegration:
    """Full pipeline lifecycle via the real DB."""

    async def test_create_and_get_pipeline(self, async_session, tenant_id):
        result = await pipeline_service.create_pipeline(
            async_session,
            tenant_id=tenant_id,
            name="Deal Pipeline",
            description="Main sales pipeline",
        )
        assert result.status == 201, f"Expected 201, got {result.status}"
        data = result.data
        assert data["name"] == "Deal Pipeline"
        assert data["tenant_id"] == tenant_id

        # Fetch it back
        fetched = await pipeline_service.get_pipeline(
            async_session, tenant_id, data["id"]
        )
        assert fetched.status == 200
        assert fetched.data["name"] == "Deal Pipeline"

    async def test_pipeline_cross_tenant_isolation(
        self, async_session, tenant_id, tenant_id_2
    ):
        p1 = await pipeline_service.create_pipeline(
            async_session,
            tenant_id=tenant_id,
            name="Tenant 1 Pipeline",
        )
        p2 = await pipeline_service.create_pipeline(
            async_session,
            tenant_id=tenant_id_2,
            name="Tenant 2 Pipeline",
        )
        assert p1.status == 201
        assert p2.status == 201

        # Tenant 1 should NOT see Tenant 2's pipeline
        list_t1 = await pipeline_service.list_pipelines(async_session, tenant_id)
        ids_t1 = [p["id"] for p in list_t1.data["pipelines"]]
        assert p2.data["id"] not in ids_t1

        # Tenant 2 should NOT see Tenant 1's pipeline
        list_t2 = await pipeline_service.list_pipelines(async_session, tenant_id_2)
        ids_t2 = [p["id"] for p in list_t2.data["pipelines"]]
        assert p1.data["id"] not in ids_t2

    async def test_update_and_delete_pipeline(self, async_session, tenant_id):
        created = await pipeline_service.create_pipeline(
            async_session,
            tenant_id=tenant_id,
            name="Original Name",
        )
        pid = created.data["id"]

        updated = await pipeline_service.update_pipeline(
            async_session, tenant_id, pid, name="Updated Name"
        )
        assert updated.status == 200
        assert updated.data["name"] == "Updated Name"

        deleted = await pipeline_service.delete_pipeline(
            async_session, tenant_id, pid
        )
        assert deleted.status == 200

        gone = await pipeline_service.get_pipeline(async_session, tenant_id, pid)
        assert gone.status == 404


# ──────────────────────────────────────────────────────────────────────────────────────
#  Customer integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestCustomerIntegration:
    """Full customer CRUD via the real DB."""

    async def test_create_and_get_customer(self, async_session, tenant_id):
        result = await customer_service.create_customer(
            async_session,
            tenant_id=tenant_id,
            name="Acme Corp",
            email="acme@example.com",
            phone="+1-555-0001",
        )
        assert result.status == 201
        data = result.data
        assert data["name"] == "Acme Corp"

        fetched = await customer_service.get_customer(
            async_session, tenant_id, data["id"]
        )
        assert fetched.status == 200
        assert fetched.data["email"] == "acme@example.com"

    async def test_customer_not_found_returns_404(self, async_session, tenant_id):
        result = await customer_service.get_customer(
            async_session, tenant_id, str(uuid.uuid4())
        )
        assert result.status == 404

    async def test_customer_cross_tenant_isolation(
        self, async_session, tenant_id, tenant_id_2
    ):
        c1 = await customer_service.create_customer(
            async_session,
            tenant_id=tenant_id,
            name="Customer One",
            email="c1@example.com",
        )
        c2 = await customer_service.create_customer(
            async_session,
            tenant_id=tenant_id_2,
            name="Customer Two",
            email="c2@example.com",
        )
        list_t1 = await customer_service.list_customers(async_session, tenant_id)
        ids = [c["id"] for c in list_t1.data["customers"]]
        assert c2.data["id"] not in ids


# ──────────────────────────────────────────────────────────────────────────────────────
#  User integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestUserIntegration:
    """Full user lifecycle via the real DB."""

    async def test_register_and_authenticate_user(self, async_session, tenant_id):
        reg = await user_service.register_user(
            async_session,
            tenant_id=tenant_id,
            username="testuser",
            email="test@example.com",
            password="Test@Pass1234",
        )
        assert reg.status == 201, f"Expected 201, got {reg.status}: {reg.data}"

        auth = await auth_service.authenticate(
            async_session,
            tenant_id=tenant_id,
            email="test@example.com",
            password="Test@Pass1234",
        )
        assert auth.status == 200, f"Auth failed: {auth.data}"
        assert "token" in auth.data or "access_token" in auth.data

    async def test_login_wrong_password_returns_401(
        self, async_session, tenant_id
    ):
        await user_service.register_user(
            async_session,
            tenant_id=tenant_id,
            username="wrongpw",
            email="wrongpw@example.com",
            password="CorrectPass@1",
        )
        auth = await auth_service.authenticate(
            async_session,
            tenant_id=tenant_id,
            email="wrongpw@example.com",
            password="WrongPassword",
        )
        assert auth.status == 401


# ──────────────────────────────────────────────────────────────────────────────────────
#  Sales / Opportunity integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestSalesIntegration:
    """Opportunity CRUD via the real DB."""

    async def test_create_and_get_opportunity(self, async_session, tenant_id):
        cust = await customer_service.create_customer(
            async_session,
            tenant_id=tenant_id,
            name="Opp Customer",
            email="opp@example.com",
        )
        cid = cust.data["id"]

        opp = await sales_service.create_opportunity(
            async_session,
            tenant_id=tenant_id,
            customer_id=cid,
            title="Big Deal",
            amount=50000.0,
        )
        assert opp.status == 201

        fetched = await sales_service.get_opportunity(
            async_session, tenant_id, opp.data["id"]
        )
        assert fetched.status == 200
        assert fetched.data["title"] == "Big Deal"

    async def test_update_opportunity_stage(self, async_session, tenant_id):
        cust = await customer_service.create_customer(
            async_session,
            tenant_id=tenant_id,
            name="Stage Test",
            email="stage@example.com",
        )
        opp = await sales_service.create_opportunity(
            async_session,
            tenant_id=tenant_id,
            customer_id=cust.data["id"],
            title="Moving Opp",
            amount=1000.0,
        )
        oid = opp.data["id"]

        updated = await sales_service.update_opportunity(
            async_session, tenant_id, oid, stage="closed_won"
        )
        assert updated.status == 200
        assert updated.data["stage"] == "closed_won"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Ticket integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTicketIntegration:
    """Ticket CRUD via the real DB."""

    async def test_create_and_get_ticket(self, async_session, tenant_id):
        result = await ticket_service.create_ticket(
            async_session,
            tenant_id=tenant_id,
            title="Critical Bug",
            description="App is down",
            priority="high",
        )
        assert result.status == 201
        assert result.data["status"] == "open"

        fetched = await ticket_service.get_ticket(
            async_session, tenant_id, result.data["id"]
        )
        assert fetched.status == 200
        assert fetched.data["priority"] == "high"

    async def test_update_ticket_status(self, async_session, tenant_id):
        tkt = await ticket_service.create_ticket(
            async_session,
            tenant_id=tenant_id,
            title="Issue",
            description="Needs fix",
            priority="medium",
        )
        oid = tkt.data["id"]

        updated = await ticket_service.update_ticket(
            async_session, tenant_id, oid, status="closed"
        )
        assert updated.status == 200
        assert updated.data["status"] == "closed"

    async def test_list_tickets_with_filters(self, async_session, tenant_id):
        await ticket_service.create_ticket(
            async_session,
            tenant_id=tenant_id,
            title="P1 Bug",
            description="",
            priority="high",
        )
        await ticket_service.create_ticket(
            async_session,
            tenant_id=tenant_id,
            title="P2 Bug",
            description="",
            priority="low",
        )

        # Filter by priority
        result = await ticket_service.list_tickets(
            async_session, tenant_id, priority="high"
        )
        assert result.status == 200
        assert all(t["priority"] == "high" for t in result.data["tickets"])
