"""
Integration tests using a real PostgreSQL database.

All service calls use the current class-based service APIs. Each test
exercises a full code path against the test database.

Run with:  pytest tests/integration/ -v
"""
from __future__ import annotations

import uuid

import pytest

from models.response import ResponseStatus
from models.ticket import TicketChannel, TicketPriority, TicketStatus
from services.auth_service import AuthService
from services.customer_service import CustomerService
from services.pipeline_service import PipelineService
from services.sales_service import SalesService
from services.ticket_service import TicketService
from services.user_service import UserService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Pipeline integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestPipelineIntegration:
    """Full pipeline lifecycle via the real DB."""

    async def test_create_and_get_pipeline(self, db_schema, tenant_id, async_session):
        svc = PipelineService(async_session)
        result = await svc.create_pipeline(
            tenant_id=tenant_id,
            data={"name": "Deal Pipeline", "description": "Main sales pipeline"},
        )
        assert result.status == ResponseStatus.SUCCESS, f"Got: {result.status}, {result.message}"
        data = result.data
        assert data["name"] == "Deal Pipeline"
        assert data["tenant_id"] == tenant_id

        fetched = await svc.get_pipeline(tenant_id, data["id"])
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == "Deal Pipeline"

    async def test_pipeline_cross_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2, async_session
    ):
        svc = PipelineService(async_session)
        p1 = await svc.create_pipeline(tenant_id=tenant_id, data={"name": "Tenant 1 Pipeline"})
        p2 = await svc.create_pipeline(tenant_id=tenant_id_2, data={"name": "Tenant 2 Pipeline"})
        assert p1.status == ResponseStatus.SUCCESS
        assert p2.status == ResponseStatus.SUCCESS

        list_t1 = await svc.list_pipelines(tenant_id)
        ids_t1 = [p["id"] for p in list_t1.data.items]
        assert p2.data["id"] not in ids_t1

        list_t2 = await svc.list_pipelines(tenant_id_2)
        ids_t2 = [p["id"] for p in list_t2.data.items]
        assert p1.data["id"] not in ids_t2

    async def test_update_and_delete_pipeline(self, db_schema, tenant_id, async_session):
        svc = PipelineService(async_session)
        created = await svc.create_pipeline(tenant_id=tenant_id, data={"name": "Original Name"})
        pid = created.data["id"]

        updated = await svc.update_pipeline(tenant_id, pid, data={"name": "Updated Name"})
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["name"] == "Updated Name"

        deleted = await svc.delete_pipeline(tenant_id, pid)
        assert deleted.status == ResponseStatus.SUCCESS

        gone = await svc.get_pipeline(tenant_id, pid)
        assert gone.status == ResponseStatus.NOT_FOUND


# ──────────────────────────────────────────────────────────────────────────────────────
#  Customer integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestCustomerIntegration:
    """Full customer CRUD via the real DB."""

    async def test_create_and_get_customer(self, db_schema, tenant_id, async_session):
        svc = CustomerService(async_session)
        result = await svc.create_customer(
            data={
                "name": "Acme Corp",
                "email": "acme@example.com",
                "phone": "+1-555-0001",
            },
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        data = result.data
        assert data["name"] == "Acme Corp"

        fetched = await svc.get_customer(customer_id=data["id"], tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["email"] == "acme@example.com"

    async def test_customer_not_found_returns_404(self, db_schema, tenant_id, async_session):
        svc = CustomerService(async_session)
        result = await svc.get_customer(customer_id=999_999_999, tenant_id=tenant_id)
        assert result.status == ResponseStatus.NOT_FOUND

    async def test_customer_cross_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2, async_session
    ):
        svc = CustomerService(async_session)
        c1 = await svc.create_customer(
            data={"name": "Customer One", "email": "c1@example.com"},
            tenant_id=tenant_id,
        )
        c2 = await svc.create_customer(
            data={"name": "Customer Two", "email": "c2@example.com"},
            tenant_id=tenant_id_2,
        )
        list_t1 = await svc.list_customers(tenant_id=tenant_id)
        ids = [c["id"] for c in list_t1.data.items]
        assert c2.data["id"] not in ids
        assert c1.data["id"] in ids


# ──────────────────────────────────────────────────────────────────────────────────────
#  User integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestUserIntegration:
    """Full user lifecycle via the real DB."""

    async def test_register_and_authenticate_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        auth_svc = AuthService(async_session)
        suffix = uuid.uuid4().hex[:8]
        username = f"user_{suffix}"
        email = f"user_{suffix}@example.com"

        reg = await user_svc.create_user(
            username=username,
            email=email,
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        assert reg.status == ResponseStatus.SUCCESS, f"Registration failed: {reg.message}"

        auth = await auth_svc.authenticate_user(
            username=username, password="Test@Pass1234"
        )
        assert auth is not None, "authenticate_user should return a user dict on success"
        assert auth["username"] == username

    async def test_login_wrong_password_returns_none(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        auth_svc = AuthService(async_session)
        suffix = uuid.uuid4().hex[:8]
        username = f"wrongpw_{suffix}"

        await user_svc.create_user(
            username=username,
            email=f"{username}@example.com",
            password="CorrectPass@1",
            tenant_id=tenant_id,
        )
        auth = await auth_svc.authenticate_user(username=username, password="WrongPassword")
        assert auth is None


# ──────────────────────────────────────────────────────────────────────────────────────
#  Sales / Opportunity integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestSalesIntegration:
    """Opportunity CRUD via the real DB."""

    async def _setup_pipeline_and_customer(self, tenant_id, session):
        cust_svc = CustomerService(session)
        pipe_svc = PipelineService(session)
        suffix = uuid.uuid4().hex[:8]
        cust = await cust_svc.create_customer(
            data={"name": f"Opp Cust {suffix}", "email": f"opp_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        pipe = await pipe_svc.create_pipeline(
            tenant_id=tenant_id, data={"name": f"Sales Pipeline {suffix}"}
        )
        assert cust.status == ResponseStatus.SUCCESS
        assert pipe.status == ResponseStatus.SUCCESS
        return cust.data["id"], pipe.data["id"]

    async def test_create_and_get_opportunity(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        cid, pid = await self._setup_pipeline_and_customer(tenant_id, async_session)

        opp = await sales_svc.create_opportunity(
            tenant_id=tenant_id,
            data={
                "name": "Big Deal",
                "customer_id": cid,
                "pipeline_id": pid,
                "stage": "qualified",
                "amount": 50000.0,
                "owner_id": 1,
            },
        )
        assert opp.status == ResponseStatus.SUCCESS, f"Failed: {opp.message}"

        fetched = await sales_svc.get_opportunity(tenant_id, opp.data["id"])
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == "Big Deal"

    async def test_update_opportunity_stage(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        cid, pid = await self._setup_pipeline_and_customer(tenant_id, async_session)

        opp = await sales_svc.create_opportunity(
            tenant_id=tenant_id,
            data={
                "name": "Moving Opp",
                "customer_id": cid,
                "pipeline_id": pid,
                "stage": "qualified",
                "amount": 1000.0,
                "owner_id": 1,
            },
        )
        oid = opp.data["id"]

        updated = await sales_svc.update_opportunity(
            tenant_id, oid, data={"stage": "closed_won"}
        )
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["stage"] == "closed_won"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Ticket integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTicketIntegration:
    """Ticket CRUD via the real DB."""

    async def _ensure_customer(self, tenant_id, session) -> int:
        svc = CustomerService(session)
        result = await svc.create_customer(
            data={"name": "Ticket Cust", "email": f"tc_{uuid.uuid4().hex[:8]}@example.com"},
            tenant_id=tenant_id,
        )
        return result.data["id"]

    async def test_create_and_get_ticket(self, db_schema, tenant_id, async_session):
        svc = TicketService(async_session)
        cid = await self._ensure_customer(tenant_id, async_session)

        result = await svc.create_ticket(
            subject="Critical Bug",
            description="App is down",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        assert result.data.status == TicketStatus.OPEN

        fetched = await svc.get_ticket(ticket_id=result.data.id, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data.priority == TicketPriority.HIGH

    async def test_update_ticket_status(self, db_schema, tenant_id, async_session):
        svc = TicketService(async_session)
        cid = await self._ensure_customer(tenant_id, async_session)

        tkt = await svc.create_ticket(
            subject="Issue",
            description="Needs fix",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            tenant_id=tenant_id,
        )
        oid = tkt.data.id

        updated = await svc.update_ticket(
            ticket_id=oid, tenant_id=tenant_id, status=TicketStatus.CLOSED
        )
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.status == TicketStatus.CLOSED

    async def test_list_tickets_with_filters(self, db_schema, tenant_id, async_session):
        svc = TicketService(async_session)
        cid = await self._ensure_customer(tenant_id, async_session)

        await svc.create_ticket(
            subject="P1 Bug",
            description="",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        await svc.create_ticket(
            subject="P2 Bug",
            description="",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )

        result = await svc.list_tickets(
            tenant_id=tenant_id, priority=TicketPriority.HIGH
        )
        assert result.status == ResponseStatus.SUCCESS
        assert all(t.priority == TicketPriority.HIGH for t in result.data.items)