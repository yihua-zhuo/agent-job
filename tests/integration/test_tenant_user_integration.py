"""
Integration tests for TenantService, UserService, TicketService & SLAService.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_tenant_user_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest
from models.response import ResponseStatus
from services.auth_service import AuthService
from services.customer_service import CustomerService
from services.sla_service import SLAService
from services.tenant_service import TenantService
from services.ticket_service import TicketService
from services.user_service import UserService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────────────


async def _seed_tenant() -> int:
    suffix = uuid.uuid4().hex[:8]
    result = await TenantService().create_tenant(
        name=f"Test Tenant {suffix}",
        plan="pro",
        admin_email=f"admin_{suffix}@example.com",
    )
    return result.data["id"]


async def _seed_user(async_session, tenant_id: int = 1, **overrides) -> int:
    user_svc = UserService()
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=overrides.get("username", f"u_{suffix}"),
        email=overrides.get("email", f"u_{suffix}@example.com"),
        password=overrides.get("password", "Test@Pass1234"),
        tenant_id=tenant_id,
    )
    return reg.data.id


# ──────────────────────────────────────────────────────────────────────────────────────
#  TenantService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTenantServiceIntegration:
    """Full tenant lifecycle via the real DB."""

    async def test_create_and_get_tenant(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        result = await svc.create_tenant(
            name=f"Tenant Create {suffix}",
            plan="enterprise",
            admin_email=f"ent_{suffix}@example.com",
        )
        assert result.status == ResponseStatus.SUCCESS
        tid = result.data["id"]

        fetched = await svc.get_tenant(tid)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == f"Tenant Create {suffix}"
        assert fetched.data["plan"] == "enterprise"

    async def test_update_tenant(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Old {suffix}",
            plan="free",
            admin_email=f"old_{suffix}@example.com",
        )
        tid = created.data["id"]

        updated = await svc.update_tenant(tid, plan="pro", name=f"Tenant New {suffix}")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["plan"] == "pro"
        assert updated.data["name"] == f"Tenant New {suffix}"

    async def test_list_tenants(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        for i in range(2):
            await svc.create_tenant(
                name=f"Tenant List {suffix} {i}",
                plan="pro",
                admin_email=f"list_{suffix}_{i}@example.com",
            )

        result = await svc.list_tenants()
        assert result.status == ResponseStatus.SUCCESS
        assert any(f"Tenant List {suffix}" in t["name"] for t in result.data["items"])

    async def test_delete_tenant(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Del {suffix}",
            plan="pro",
            admin_email=f"del_{suffix}@example.com",
        )
        tid = created.data["id"]

        deleted = await svc.delete_tenant(tid)
        assert deleted.status == ResponseStatus.SUCCESS

        fetched = await svc.get_tenant(tid)
        assert fetched.status == ResponseStatus.ERROR

    async def test_get_tenant_stats(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Stats {suffix}",
            plan="pro",
            admin_email=f"stats_{suffix}@example.com",
        )
        tid = created.data["id"]

        stats = await svc.get_tenant_stats(tid)
        assert stats.status == ResponseStatus.SUCCESS
        assert isinstance(stats.data, dict)

    async def test_get_tenant_usage(self, db_schema, tenant_id):
        svc = TenantService()
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Usage {suffix}",
            plan="pro",
            admin_email=f"usage_{suffix}@example.com",
        )
        tid = created.data["id"]

        usage = await svc.get_tenant_usage(tid)
        assert usage.status == ResponseStatus.SUCCESS


# ──────────────────────────────────────────────────────────────────────────────────────
#  UserService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestUserServiceIntegration:
    """Full user lifecycle via the real DB using the shared async_session fixture."""

    async def test_create_and_get_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"ug_{suffix}",
            email=f"ug_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        assert reg.status == ResponseStatus.SUCCESS
        uid = reg.data.id

        fetched = await user_svc.get_user_by_id(uid)
        assert fetched is not None
        assert fetched.username == f"ug_{suffix}"

    async def test_get_user_by_username(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        await user_svc.create_user(
            username=f"ub_{suffix}",
            email=f"ub_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )

        fetched = await user_svc.get_user_by_username(f"ub_{suffix}")
        assert fetched is not None
        assert fetched.email == f"ub_{suffix}@example.com"

    async def test_get_user_by_email(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        await user_svc.create_user(
            username=f"ue_{suffix}",
            email=f"ue_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )

        fetched = await user_svc.get_user_by_email(f"ue_{suffix}@example.com")
        assert fetched is not None
        assert fetched.username == f"ue_{suffix}"

    async def test_update_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"up_{suffix}",
            email=f"up_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = reg.data.id

        updated = await user_svc.update_user(uid, username=f"upd_{suffix}")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.username == f"upd_{suffix}"

    async def test_delete_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"ud_{suffix}",
            email=f"ud_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = reg.data.id

        deleted = await user_svc.delete_user(uid)
        assert deleted.status == ResponseStatus.SUCCESS

        fetched = await user_svc.get_user_by_id(uid)
        assert fetched is None

    async def test_list_users(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        for i in range(2):
            await user_svc.create_user(
                username=f"lu_{suffix}_{i}",
                email=f"lu_{suffix}_{i}@example.com",
                password="Test@Pass1234",
                tenant_id=tenant_id,
            )

        result = await user_svc.list_users(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        assert any(f"lu_{suffix}_0" in u.username for u in result.data["items"])

    async def test_search_users(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        await user_svc.create_user(
            username=f"su_{suffix}",
            email=f"su_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )

        result = await user_svc.search_users(suffix)
        assert result.status == ResponseStatus.SUCCESS
        assert any(suffix in u.username for u in result.data["items"])

    async def test_change_password(self, db_schema, tenant_id, async_session):
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"cp_{suffix}",
            email=f"cp_{suffix}@example.com",
            password="Old@Pass1234",
            tenant_id=tenant_id,
        )
        uid = reg.data.id

        changed = await user_svc.change_password(uid, "New@Pass5678")
        assert changed.status == ResponseStatus.SUCCESS


# ──────────────────────────────────────────────────────────────────────────────────────
#  TicketService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTicketServiceIntegration:
    """Full ticket lifecycle via the real DB using the shared async_session fixture."""

    async def test_create_and_get_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        result = await ticket_svc.create_ticket(
            customer_id=cid,
            title="Support Issue",
            description="Cannot login",
            priority="high",
            created_by=uid,
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        tid = result.data.id

        fetched = await ticket_svc.get_ticket(tid, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data.title == "Support Issue"

    async def test_update_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            customer_id=cid,
            title="Original Title",
            description="Original Desc",
            priority="low",
            created_by=uid,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        updated = await ticket_svc.update_ticket(tid, title="Updated Title", priority="high", tenant_id=tenant_id)
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.title == "Updated Title"

    async def test_assign_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            customer_id=cid,
            title="To Assign",
            description="Assign me",
            priority="medium",
            created_by=uid,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        assigned = await ticket_svc.assign_ticket(tid, uid, tenant_id=tenant_id)
        assert assigned.status == ResponseStatus.SUCCESS

    async def test_add_reply(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            customer_id=cid,
            title="Reply Test",
            description="Add a reply",
            priority="low",
            created_by=uid,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        reply = await ticket_svc.add_reply(tid, content="Here is the fix", author_id=uid, tenant_id=tenant_id)
        assert reply.status == ResponseStatus.SUCCESS
        assert reply.data.content == "Here is the fix"

    async def test_change_ticket_status(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            customer_id=cid,
            title="Status Test",
            description="Change my status",
            priority="low",
            created_by=uid,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        changed = await ticket_svc.change_status(tid, "in_progress", tenant_id=tenant_id)
        assert changed.status == ResponseStatus.SUCCESS
        assert changed.data.status.value == "in_progress"

    async def test_list_tickets(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        suffix = uuid.uuid4().hex[:8]
        for i in range(2):
            await ticket_svc.create_ticket(
                customer_id=cid,
                title=f"List Ticket {suffix} {i}",
                description="List me",
                priority="low",
                created_by=uid,
                tenant_id=tenant_id,
            )

        result = await ticket_svc.list_tickets(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        assert any(f"List Ticket {suffix}" in t.title for t in result.data["items"])

    async def test_get_customer_tickets(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        await ticket_svc.create_ticket(
            customer_id=cid,
            title="Customer Ticket",
            description="For this customer",
            priority="medium",
            created_by=uid,
            tenant_id=tenant_id,
        )

        result = await ticket_svc.get_customer_tickets(cid, tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS

    async def test_get_sla_breaches(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        await ticket_svc.create_ticket(
            customer_id=cid,
            title="SLA Breach Test",
            description="Check SLA",
            priority="high",
            created_by=uid,
            tenant_id=tenant_id,
        )

        breaches = await ticket_svc.get_sla_breaches(tenant_id=tenant_id)
        assert isinstance(breaches, list)


# ──────────────────────────────────────────────────────────────────────────────────────
#  SLAService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestSLAServiceIntegration:
    """SLA breach checking via the real DB using the shared async_session fixture."""

    async def test_check_sla_status(self, db_schema, tenant_id, async_session):
        sla_svc = SLAService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        ticket_svc = TicketService()
        created = await ticket_svc.create_ticket(
            customer_id=cid,
            title="SLA Status Check",
            description="Check SLA status",
            priority="high",
            created_by=uid,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        status = await sla_svc.check_sla_status(tid, tenant_id=tenant_id)
        assert status is not None

    async def test_get_breach_tickets(self, db_schema, tenant_id, async_session):
        sla_svc = SLAService()
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        ticket_svc = TicketService()
        await ticket_svc.create_ticket(
            customer_id=cid,
            title="SLA Breach Tickets",
            description="Check breach list",
            priority="critical",
            created_by=uid,
            tenant_id=tenant_id,
        )

        breaches = await sla_svc.get_breach_tickets(tenant_id=tenant_id)
        assert isinstance(breaches, list)


# ──────────────────────────────────────────────────────────────────────────────────────
#  AuthService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestAuthServiceIntegration:
    """Auth service (password hashing / JWT) via the real DB using the shared async_session fixture."""

    async def test_create_user_with_auth(self, db_schema, tenant_id, async_session):
        auth_svc = AuthService()
        suffix = uuid.uuid4().hex[:8]
        result = await auth_svc.register(
            username=f"auth_{suffix}",
            email=f"auth_{suffix}@example.com",
            password="Secure@Pass1234",
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        assert result.data["username"] == f"auth_{suffix}"

    async def test_login(self, db_schema, tenant_id, async_session):
        auth_svc = AuthService()
        suffix = uuid.uuid4().hex[:8]
        await auth_svc.register(
            username=f"login_{suffix}",
            email=f"login_{suffix}@example.com",
            password="Secure@Pass1234",
            tenant_id=tenant_id,
        )

        result = await auth_svc.login(
            username=f"login_{suffix}",
            password="Secure@Pass1234",
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        assert "access_token" in result.data or hasattr(result.data, "access_token")


async def _seed_customer(async_session, tenant_id: int = 1, **overrides) -> dict:
    cust_svc = CustomerService(async_session)
    suffix = uuid.uuid4().hex[:8]
    data = {"name": f"SC Cust {suffix}", "email": f"sc_{suffix}@example.com", **overrides}
    result = await cust_svc.create_customer(data=data, tenant_id=tenant_id)
    return result
