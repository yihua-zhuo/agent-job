"""
Integration tests for TenantService, UserService, TicketService, SLAService & AuthService.

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
from services.ticket_service import TicketChannel, TicketPriority, TicketService, TicketStatus
from services.user_service import UserService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────────────


async def _seed_tenant() -> int:
    suffix = uuid.uuid4().hex[:8]
    result = await TenantService(async_session).create_tenant(
        name=f"Test Tenant {suffix}",
        plan="pro",
        admin_email=f"admin_{suffix}@example.com",
    )
    return result.data["id"]


async def _seed_user(async_session, tenant_id: int = 1, **overrides) -> int:
    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=overrides.get("username", f"u_{suffix}"),
        email=overrides.get("email", f"u_{suffix}@example.com"),
        password=overrides.get("password", "Test@Pass1234"),
        tenant_id=tenant_id,
    )
    return reg.data.id


async def _seed_customer(async_session, tenant_id: int = 1, **overrides) -> dict:
    cust_svc = CustomerService(async_session)
    suffix = uuid.uuid4().hex[:8]
    data = {"name": f"SC Cust {suffix}", "email": f"sc_{suffix}@example.com", **overrides}
    result = await cust_svc.create_customer(data=data, tenant_id=tenant_id)
    return result


# ──────────────────────────────────────────────────────────────────────────────────────
#  TenantService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTenantServiceIntegration:
    """Full tenant lifecycle via the real DB."""

    async def test_create_and_get_tenant(self, db_schema, tenant_id, async_session):
        svc = TenantService(async_session)
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

    async def test_update_tenant(self, db_schema, tenant_id, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Old {suffix}",
            plan="free",
            admin_email=f"old_{suffix}@example.com",
        )
        tid = created.data["id"]

        updated = await svc.update_tenant(tid, name=f"Tenant New {suffix}", plan="pro")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["name"] == f"Tenant New {suffix}"

    async def test_delete_tenant(self, db_schema, tenant_id, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Tenant Del {suffix}",
            plan="free",
            admin_email=f"del_{suffix}@example.com",
        )
        tid = created.data["id"]

        deleted = await svc.delete_tenant(tid)
        assert deleted.status == ResponseStatus.SUCCESS

        fetched = await svc.get_tenant(tid)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["status"] == "deleted"

    async def test_list_tenants(self, db_schema, tenant_id, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        for name in [f"List Ten {suffix} A", f"List Ten {suffix} B"]:
            await svc.create_tenant(name=name, plan="free", admin_email=f"{name.lower().replace(' ', '_')}@example.com")

        result = await svc.list_tenants(page=1, page_size=20)
        assert result.status == ResponseStatus.SUCCESS
        assert len(result.data.items) >= 2

    async def test_get_tenant_stats(self, db_schema, tenant_id, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Stats Ten {suffix}",
            plan="free",
            admin_email=f"stats_{suffix}@example.com",
        )
        tid = created.data["id"]
        stats = await svc.get_tenant_stats(tid)
        assert stats.status == ResponseStatus.SUCCESS
        assert isinstance(stats.data, dict)


# ──────────────────────────────────────────────────────────────────────────────────────
#  UserService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestUserServiceIntegration:
    """Full user lifecycle via the real DB."""

    async def test_create_and_get_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await user_svc.create_user(
            username=f"cu_{suffix}",
            email=f"cu_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        uid = result.data.id

        fetched = await user_svc.get_user_by_id(uid)
        assert fetched is not None
        assert fetched.username == f"cu_{suffix}"

    async def test_get_user_by_username(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await user_svc.create_user(
            username=f"un_{suffix}",
            email=f"un_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )

        fetched = await user_svc.get_user_by_username(f"un_{suffix}")
        assert fetched is not None
        assert fetched.username == f"un_{suffix}"

    async def test_update_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await user_svc.create_user(
            username=f"uu_{suffix}",
            email=f"uu_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = created.data.id

        updated = await user_svc.update_user(uid, bio="Updated bio")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.bio == "Updated bio"

    async def test_delete_user(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await user_svc.create_user(
            username=f"du_{suffix}",
            email=f"du_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = created.data.id

        deleted = await user_svc.delete_user(uid)
        assert deleted.status == ResponseStatus.SUCCESS

        fetched = await user_svc.get_user_by_id(uid)
        assert fetched is None

    async def test_list_users(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        for i in range(2):
            await user_svc.create_user(
                username=f"lu_{suffix}_{i}",
                email=f"lu_{suffix}_{i}@example.com",
                password="Test@Pass1234",
                tenant_id=tenant_id,
            )

        # list_users() returns PaginatedData[User]; User objects have .username
        result = await user_svc.list_users(page=1, page_size=20)
        assert result.status == ResponseStatus.SUCCESS
        assert len(result.data.items) >= 2
        assert any(u.username == f"lu_{suffix}_0" for u in result.data.items)

    async def test_search_users(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await user_svc.create_user(
            username=f"su_{suffix}",
            email=f"su_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )

        result = await user_svc.search_users(suffix)
        assert result.status == ResponseStatus.SUCCESS
        assert any(suffix in u.username for u in result.data.items)

    async def test_change_password(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"cp_{suffix}",
            email=f"cp_{suffix}@example.com",
            password="Old@Pass1234",
            tenant_id=tenant_id,
        )
        uid = reg.data.id

        # Signature: change_password(user_id, old_password, new_password)
        changed = await user_svc.change_password(uid, "Old@Pass1234", "New@Pass5678")
        assert changed.status == ResponseStatus.SUCCESS


# ──────────────────────────────────────────────────────────────────────────────────────
#  TicketService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTicketServiceIntegration:
    """Full ticket lifecycle via the real DB using the shared async_session fixture."""

    async def test_create_and_get_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        result = await ticket_svc.create_ticket(
            subject="Support Issue",
            description="Cannot login",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        tid = result.data.id

        fetched = await ticket_svc.get_ticket(tid, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data.subject == "Support Issue"

    async def test_update_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            subject="Original Title",
            description="Original Desc",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        # update_ticket(ticket_id, tenant_id=0, **kwargs)
        updated = await ticket_svc.update_ticket(tid, tenant_id=tenant_id, subject="Updated Title", priority=TicketPriority.HIGH)
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.subject == "Updated Title"

    async def test_assign_ticket(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            subject="To Assign",
            description="Assign me",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        assigned = await ticket_svc.assign_ticket(tid, uid, tenant_id=tenant_id)
        assert assigned.status == ResponseStatus.SUCCESS

    async def test_add_reply(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            subject="Reply Test",
            description="Add a reply",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        # add_reply(ticket_id, content, created_by, is_internal=False, tenant_id=0)
        reply = await ticket_svc.add_reply(tid, "Here is the fix", created_by=uid, tenant_id=tenant_id)
        assert reply.status == ResponseStatus.SUCCESS
        assert reply.data.content == "Here is the fix"

    async def test_change_ticket_status(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            subject="Status Test",
            description="Change my status",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        # change_status(ticket_id, new_status: TicketStatus, tenant_id=0)
        changed = await ticket_svc.change_status(tid, TicketStatus.IN_PROGRESS, tenant_id=tenant_id)
        assert changed.status == ResponseStatus.SUCCESS
        assert changed.data.status == TicketStatus.IN_PROGRESS

    async def test_list_tickets(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        suffix = uuid.uuid4().hex[:8]
        for i in range(2):
            await ticket_svc.create_ticket(
                subject=f"List Ticket {suffix} {i}",
                description="List me",
                customer_id=cid,
                channel=TicketChannel.EMAIL,
                priority=TicketPriority.LOW,
                tenant_id=tenant_id,
            )

        result = await ticket_svc.list_tickets(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        assert any(f"List Ticket {suffix}" in t.subject for t in result.data.items)

    async def test_get_customer_tickets(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        await ticket_svc.create_ticket(
            subject="Customer Ticket",
            description="For this customer",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            tenant_id=tenant_id,
        )

        # get_customer_tickets returns List[Ticket] directly, not ApiResponse
        result = await ticket_svc.get_customer_tickets(cid, tenant_id=tenant_id)
        assert len(result) >= 1

    async def test_get_sla_breaches(self, db_schema, tenant_id, async_session):
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        await ticket_svc.create_ticket(
            subject="SLA Breach Test",
            description="Check SLA",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )

        # get_sla_breaches returns List[Ticket] directly, not ApiResponse
        breaches = await ticket_svc.get_sla_breaches(tenant_id=tenant_id)
        assert isinstance(breaches, list)


# ──────────────────────────────────────────────────────────────────────────────────────
#  SLAService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestSLAServiceIntegration:
    """SLA breach checking via the real DB using the shared async_session fixture."""

    async def test_check_sla_status(self, db_schema, tenant_id, async_session):
        sla_svc = SLAService(async_session)
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        created = await ticket_svc.create_ticket(
            subject="SLA Status Check",
            description="Check SLA status",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )
        tid = created.data.id

        # check_sla_status(ticket: Ticket) — fetch the Ticket object first
        fetched = await ticket_svc.get_ticket(tid, tenant_id=tenant_id)
        status = await sla_svc.check_sla_status(fetched.data)
        assert status in ("normal", "warning", "breached")

    async def test_get_breach_tickets(self, db_schema, tenant_id, async_session):
        sla_svc = SLAService(async_session)
        ticket_svc = TicketService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        cid = (await _seed_customer(async_session, tenant_id)).data["id"]
        await ticket_svc.create_ticket(
            subject="SLA Breach Tickets",
            description="Check breach list",
            customer_id=cid,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.URGENT,
            tenant_id=tenant_id,
        )

        # get_breach_tickets returns List[Ticket] directly
        breaches = await sla_svc.get_breach_tickets(tenant_id=tenant_id)
        assert isinstance(breaches, list)


# ──────────────────────────────────────────────────────────────────────────────────────
#  AuthService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestAuthServiceIntegration:
    """Auth service (password hashing / JWT) via the real DB using the shared async_session fixture."""

    async def test_create_user_with_auth(self, db_schema, tenant_id, async_session):
        auth_svc = AuthService(async_session)
        suffix = uuid.uuid4().hex[:8]
        # AuthService.create_user delegates to UserService.create_user which returns ApiResponse[User]
        result = await auth_svc.create_user(
            username=f"auth_{suffix}",
            email=f"auth_{suffix}@example.com",
            password="Secure@Pass1234",
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        assert result.data.username == f"auth_{suffix}"

    async def test_login(self, db_schema, tenant_id, async_session):
        auth_svc = AuthService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await auth_svc.create_user(
            username=f"login_{suffix}",
            email=f"login_{suffix}@example.com",
            password="Secure@Pass1234",
            tenant_id=tenant_id,
        )

        # authenticate_user returns User dict directly (no ApiResponse wrapper)
        result = await auth_svc.authenticate_user(
            username=f"login_{suffix}",
            password="Secure@Pass1234",
        )
        assert result is not None
        assert result["username"] == f"login_{suffix}"
