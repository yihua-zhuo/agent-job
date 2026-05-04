"""
Integration tests for automation_rules, data_isolation, rbac_service,
sla_service, and trigger_service.

The first three are pure in-memory services (no DB). sla_service and
trigger_service use the real PostgreSQL DB (via DATABASE_URL env var).

Run with:  export $(grep DATABASE_URL .env | xargs)
           python3 -m pytest tests/integration/test_rules_integration.py -v
"""
from __future__ import annotations

import uuid

import pytest

from models.marketing import CampaignType, TriggerType
from models.ticket import (
    SLALevel,
    Ticket,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from services.automation_rules import AutomationRules
from services.data_isolation import (
    DataIsolationError,
    TenantScope,
    get_cross_tenant_fields,
    is_cross_tenant_safe,
    require_tenant_id,
    sanitize_tenant_write,
)
from services.marketing_service import MarketingService
from services.rbac_service import Permission, RBACService
from services.sla_service import SLAService
from services.ticket_service import TicketService
from services.trigger_service import TriggerService
from services.user_service import UserService


# ==============================================================================
#  automation_rules — pure in-memory, no DB
# ==============================================================================
@pytest.mark.integration
class TestAutomationRulesIntegration:
    """AutomationRules in-memory rule engine — no database needed."""

    def test_get_available_rules_returns_all(self):
        svc = AutomationRules()
        rules = svc.get_available_rules()
        assert len(rules) == 4
        keys = {r["key"] for r in rules}
        assert "new_customer_welcome" in keys
        assert "opportunity_stage_changed" in keys
        assert "inactive_customer_alert" in keys
        assert "deal_won_celebration" in keys

    def test_get_available_rules_includes_trigger_and_actions(self):
        svc = AutomationRules()
        rules = svc.get_available_rules()
        welcome = next(r for r in rules if r["key"] == "new_customer_welcome")
        assert welcome["trigger"] == "event.customer.created"
        assert len(welcome["actions"]) == 3

    def test_apply_rule_new_customer_welcome(self):
        svc = AutomationRules()
        result = svc.apply_rule("new_customer_welcome", {"customer_id": 123})
        assert result["rule"] == "new_customer_welcome"
        assert result["rule_name_display"] == "新客户欢迎"
        assert result["trigger"] == "event.customer.created"
        assert len(result["actions_executed"]) == 3
        # email action
        email_action = next(a for a in result["actions_executed"] if a["type"] == "email.send")
        assert email_action["status"] == "sent"
        assert email_action["template"] == "welcome"
        # tag action
        tag_action = next(a for a in result["actions_executed"] if a["type"] == "tag.add")
        assert tag_action["tag"] == "new_customer"
        # task action
        task_action = next(a for a in result["actions_executed"] if a["type"] == "task.create")
        assert task_action["title"] == "新客户跟进"

    def test_apply_rule_deal_won_celebration(self):
        svc = AutomationRules()
        result = svc.apply_rule("deal_won_celebration", {"stage": "won"})
        assert result["rule"] == "deal_won_celebration"
        actions = {a["type"] for a in result["actions_executed"]}
        assert "email.send" in actions
        assert "activity.log" in actions

    def test_apply_rule_unknown_raises(self):
        svc = AutomationRules()
        with pytest.raises(ValueError, match="not found"):
            svc.apply_rule("nonexistent_rule", {})


# ==============================================================================
#  data_isolation — pure utility functions, no DB
# ==============================================================================
@pytest.mark.integration
class TestDataIsolationIntegration:
    """DataIsolation tenant-scoped helpers — no database needed."""

    def test_tenant_scope_filter_query(self):
        scope = TenantScope(tenant_id=42)
        records = [
            {"tenant_id": 42, "name": "Alice"},
            {"tenant_id": 99, "name": "Bob"},
            {"tenant_id": 42, "name": "Carol"},
        ]
        filtered = scope.filter_query(records)
        assert len(filtered) == 2
        assert all(r["tenant_id"] == 42 for r in filtered)

    def test_tenant_scope_check_ownership(self):
        scope = TenantScope(tenant_id=42)
        assert scope.check_ownership({"tenant_id": 42, "name": "Alice"}) is True
        assert scope.check_ownership({"tenant_id": 99, "name": "Bob"}) is False
        assert scope.check_ownership(None) is False

    def test_tenant_scope_rejects_invalid_tenant_id(self):
        with pytest.raises(ValueError, match="positive integer"):
            TenantScope(tenant_id=0)
        with pytest.raises(ValueError, match="positive integer"):
            TenantScope(tenant_id=-1)

    def test_require_tenant_id_decorator_success(self):
        @require_tenant_id
        def do_something(tenant_id: int) -> int:
            return tenant_id * 2

        result = do_something(tenant_id=5)
        assert result == 10

    def test_require_tenant_id_decorator_from_args(self):
        @require_tenant_id
        def fetch_data(tenant_id: int) -> str:
            return f"tenant:{tenant_id}"

        result = fetch_data(5)
        assert result == "tenant:5"

    def test_require_tenant_id_decorator_fails_on_none(self):
        @require_tenant_id
        def do_something(tenant_id: int) -> int:
            return tenant_id

        with pytest.raises(DataIsolationError, match="valid tenant_id"):
            do_something(tenant_id=None)

    def test_require_tenant_id_decorator_fails_on_zero(self):
        @require_tenant_id
        def do_something(tenant_id: int) -> int:
            return tenant_id

        with pytest.raises(DataIsolationError):
            do_something(tenant_id=0)

    def test_require_tenant_id_decorator_fails_on_negative(self):
        @require_tenant_id
        def do_something(tenant_id: int) -> int:
            return tenant_id

        with pytest.raises(DataIsolationError):
            do_something(tenant_id=-10)

    def test_sanitize_tenant_write_injects_tenant_id(self):
        data = {"name": "Test", "status": "active"}
        result = sanitize_tenant_write(data, tenant_id=7)
        assert result == {"name": "Test", "status": "active", "tenant_id": 7}
        # original unchanged
        assert "tenant_id" not in data

    def test_sanitize_tenant_write_allows_same_tenant_id(self):
        data = {"tenant_id": 7, "name": "Test"}
        result = sanitize_tenant_write(data, tenant_id=7)
        assert result["tenant_id"] == 7

    def test_sanitize_tenant_write_rejects_different_tenant(self):
        data = {"tenant_id": 99, "name": "Hacked"}
        with pytest.raises(DataIsolationError, match="different tenant"):
            sanitize_tenant_write(data, tenant_id=7)

    def test_get_cross_tenant_fields(self):
        fields = get_cross_tenant_fields()
        assert "_system_config" in fields
        assert "_global_settings" in fields

    def test_is_cross_tenant_safe(self):
        assert is_cross_tenant_safe("_system_config") is True
        assert is_cross_tenant_safe("_global_settings") is True
        assert is_cross_tenant_safe("customer_name") is False


# ==============================================================================
#  rbac_service — pure permission checks, no DB
# ==============================================================================
@pytest.mark.integration
class TestRBACServiceIntegration:
    """RBAC permission engine — no database needed."""

    @pytest.fixture(autouse=True)
    def _mock_session(self):
        from unittest.mock import MagicMock
        self._session = MagicMock()

    def test_admin_has_all_customer_permissions(self):
        svc = RBACService(self._session)
        for perm in [
            Permission.CUSTOMER_CREATE,
            Permission.CUSTOMER_READ,
            Permission.CUSTOMER_UPDATE,
            Permission.CUSTOMER_DELETE,
        ]:
            assert svc.has_permission("admin", perm) is True

    def test_admin_has_all_opportunity_permissions(self):
        svc = RBACService(self._session)
        for perm in [
            Permission.OPPORTUNITY_CREATE,
            Permission.OPPORTUNITY_READ,
            Permission.OPPORTUNITY_UPDATE,
            Permission.OPPORTUNITY_DELETE,
        ]:
            assert svc.has_permission("admin", perm) is True

    def test_admin_has_admin_permissions(self):
        svc = RBACService(self._session)
        assert svc.has_permission("admin", Permission.ADMIN_ALL) is True
        assert svc.has_permission("admin", Permission.USER_MANAGE) is True

    def test_manager_can_read_but_not_delete_customers(self):
        svc = RBACService(self._session)
        assert svc.has_permission("manager", Permission.CUSTOMER_READ) is True
        assert svc.has_permission("manager", Permission.CUSTOMER_CREATE) is False
        assert svc.has_permission("manager", Permission.CUSTOMER_DELETE) is False

    def test_manager_can_create_update_opportunities(self):
        svc = RBACService(self._session)
        assert svc.has_permission("manager", Permission.OPPORTUNITY_CREATE) is True
        assert svc.has_permission("manager", Permission.OPPORTUNITY_UPDATE) is True
        assert svc.has_permission("manager", Permission.OPPORTUNITY_DELETE) is False

    def test_sales_can_create_customers(self):
        svc = RBACService(self._session)
        assert svc.has_permission("sales", Permission.CUSTOMER_CREATE) is True
        assert svc.has_permission("sales", Permission.CUSTOMER_READ) is True
        assert svc.has_permission("sales", Permission.CUSTOMER_UPDATE) is True
        assert svc.has_permission("sales", Permission.CUSTOMER_DELETE) is False

    def test_sales_can_create_opportunities(self):
        svc = RBACService(self._session)
        assert svc.has_permission("sales", Permission.OPPORTUNITY_CREATE) is True
        assert svc.has_permission("sales", Permission.OPPORTUNITY_READ) is True
        assert svc.has_permission("sales", Permission.OPPORTUNITY_UPDATE) is True
        assert svc.has_permission("sales", Permission.OPPORTUNITY_DELETE) is False

    def test_support_read_only(self):
        svc = RBACService(self._session)
        assert svc.has_permission("support", Permission.CUSTOMER_READ) is True
        assert svc.has_permission("support", Permission.OPPORTUNITY_READ) is True
        assert svc.has_permission("support", Permission.CUSTOMER_CREATE) is False
        assert svc.has_permission("support", Permission.OPPORTUNITY_CREATE) is False

    def test_viewer_read_only(self):
        svc = RBACService(self._session)
        assert svc.has_permission("viewer", Permission.CUSTOMER_READ) is True
        assert svc.has_permission("viewer", Permission.OPPORTUNITY_READ) is True
        assert svc.has_permission("viewer", Permission.CUSTOMER_CREATE) is False

    def test_unknown_role_has_no_permissions(self):
        svc = RBACService(self._session)
        assert svc.has_permission("ghost", Permission.CUSTOMER_READ) is False
        assert svc.has_permission("", Permission.CUSTOMER_READ) is False

    def test_get_role_permissions_admin(self):
        svc = RBACService(self._session)
        perms = svc.get_role_permissions("admin")
        assert Permission.ADMIN_ALL in perms
        assert Permission.USER_MANAGE in perms
        assert Permission.CUSTOMER_READ in perms

    def test_get_role_permissions_manager(self):
        svc = RBACService(self._session)
        perms = svc.get_role_permissions("manager")
        assert Permission.CUSTOMER_READ in perms
        assert Permission.CUSTOMER_DELETE not in perms

    def test_get_role_permissions_unknown_returns_empty(self):
        svc = RBACService(self._session)
        assert svc.get_role_permissions("unknown_role") == []

    def test_check_permission_by_value_valid(self):
        svc = RBACService(self._session)
        assert svc.check_permission_by_value("admin", "customer:read") is True
        assert svc.check_permission_by_value("sales", "customer:create") is True

    def test_check_permission_by_value_invalid_role(self):
        svc = RBACService(self._session)
        assert svc.check_permission_by_value("ghost", "customer:read") is False

    def test_check_permission_by_value_invalid_permission_string(self):
        svc = RBACService(self._session)
        assert svc.check_permission_by_value("admin", "nonexistent:perm") is False


# ==============================================================================
#  sla_service — real DB, needs tickets
# ==============================================================================
@pytest.mark.integration
class TestSLAIntegration:
    """SLAService against the real DB — needs tickets table."""

    async def _seed_ticket(
        self, tenant_id: int, async_session, sla_level: SLALevel = SLALevel.STANDARD
    ) -> Ticket:
        """Create a ticket via TicketService and return the domain model."""
        ticket_svc = TicketService(async_session)
        ticket = await ticket_svc.create_ticket(
            subject=f"SLA Test Ticket {uuid.uuid4().hex[:8]}",
            description="Testing SLA status",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            sla_level=sla_level,
            tenant_id=tenant_id,
        )
        return ticket

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"slauser_{suffix}",
            email=f"sla_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.id

    async def test_check_sla_status_normal(self, db_schema, tenant_id, async_session):
        ticket = await self._seed_ticket(tenant_id, async_session, sla_level=SLALevel.PREMIUM)
        sla_svc = SLAService(async_session)
        status = sla_svc.check_sla_status(ticket)
        # Fresh ticket well within SLA window
        assert status in ("normal", "warning")

    async def test_check_sla_status_breached(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime, timedelta

        # Create a ticket that's already past response_deadline
        ticket = await self._seed_ticket(tenant_id, async_session, sla_level=SLALevel.STANDARD)
        # Manually expire it
        expired_ticket = Ticket(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            channel=TicketChannel.EMAIL,
            customer_id=ticket.customer_id,
            sla_level=ticket.sla_level,
            tenant_id=tenant_id,
            assigned_to=ticket.assigned_to,
            created_at=datetime.now(UTC) - timedelta(hours=48),
            updated_at=datetime.now(UTC) - timedelta(hours=48),
            resolved_at=None,
            first_response_at=None,
            response_deadline=datetime.now(UTC) - timedelta(hours=40),
        )
        sla_svc = SLAService(async_session)
        status = sla_svc.check_sla_status(expired_ticket)
        assert status == "breached"

    async def test_check_sla_status_resolved_is_normal(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime, timedelta

        ticket = await self._seed_ticket(tenant_id, async_session)
        # Resolved ticket is always "normal"
        resolved_ticket = Ticket(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=TicketStatus.RESOLVED,
            priority=TicketPriority.MEDIUM,
            channel=TicketChannel.EMAIL,
            customer_id=ticket.customer_id,
            sla_level=ticket.sla_level,
            tenant_id=tenant_id,
            assigned_to=ticket.assigned_to,
            created_at=datetime.now(UTC) - timedelta(hours=48),
            updated_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC) - timedelta(hours=40),
            first_response_at=datetime.now(UTC) - timedelta(hours=41),
            response_deadline=datetime.now(UTC) - timedelta(hours=40),
        )
        sla_svc = SLAService(async_session)
        status = sla_svc.check_sla_status(resolved_ticket)
        assert status == "normal"

    async def test_calculate_remaining_time_positive(self, db_schema, tenant_id, async_session):
        ticket = await self._seed_ticket(tenant_id, async_session, sla_level=SLALevel.ENTERPRISE)
        sla_svc = SLAService(async_session)
        remaining = sla_svc.calculate_remaining_time(ticket)
        assert remaining.total_seconds() > 0

    async def test_calculate_remaining_time_zero_if_resolved(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime, timedelta

        ticket = await self._seed_ticket(tenant_id, async_session)
        resolved_ticket = Ticket(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=TicketStatus.RESOLVED,
            priority=TicketPriority.MEDIUM,
            channel=TicketChannel.EMAIL,
            customer_id=ticket.customer_id,
            sla_level=ticket.sla_level,
            tenant_id=tenant_id,
            assigned_to=ticket.assigned_to,
            created_at=datetime.now(UTC) - timedelta(hours=10),
            updated_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC),
            first_response_at=datetime.now(UTC),
            response_deadline=datetime.now(UTC) + timedelta(hours=1),
        )
        sla_svc = SLAService(async_session)
        remaining = sla_svc.calculate_remaining_time(resolved_ticket)
        assert remaining == timedelta(0)

    async def test_get_breach_tickets_returns_list(self, db_schema, tenant_id, async_session):
        # Create an already-breached ticket by setting deadline in the past
        from datetime import UTC, datetime, timedelta

        ticket = await self._seed_ticket(tenant_id, async_session, sla_level=SLALevel.BASIC)
        # Force deadline to the past (in-memory ticket)
        ticket.response_deadline = datetime.now(UTC) - timedelta(hours=1)

        sla_svc = SLAService(async_session)
        breached = sla_svc.get_breach_tickets(tickets=[ticket])
        breached_ids = [t.id for t in breached]
        assert ticket.id in breached_ids


# ==============================================================================
#  trigger_service — real DB, needs MarketingService + campaigns
# ==============================================================================
@pytest.mark.integration
class TestTriggerIntegration:
    """TriggerService against the real DB — needs MarketingService + campaigns."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"triguser_{suffix}",
            email=f"trig_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.id

    async def _seed_campaign(
        self, tenant_id: int, created_by: int, trigger_type: TriggerType, async_session
    ):
        marketing_svc = MarketingService(async_session)
        return await marketing_svc.create_campaign(
            name=f"Trigger Test Campaign {uuid.uuid4().hex[:8]}",
            campaign_type=CampaignType.EMAIL,
            content="Test content",
            created_by=created_by,
            tenant_id=tenant_id,
            trigger_type=trigger_type,
        )

    async def test_check_triggers_user_register(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        campaign = await self._seed_campaign(
            tenant_id, uid, TriggerType.USER_REGISTER, async_session
        )
        marketing_svc = MarketingService(async_session)
        trigger_svc = TriggerService(marketing_svc)

        triggered_ids = await trigger_svc.check_triggers(
            "user_register", {"user_id": uid}, tenant_id=tenant_id
        )
        assert campaign.id in triggered_ids

    async def test_check_triggers_unknown_event_returns_empty(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        marketing_svc = MarketingService(async_session)
        trigger_svc = TriggerService(marketing_svc)

        triggered_ids = await trigger_svc.check_triggers(
            "unknown_event", {"user_id": uid}, tenant_id=tenant_id
        )
        assert triggered_ids == []

    async def test_check_triggers_no_matching_campaign(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        await self._seed_campaign(
            tenant_id, uid, TriggerType.PURCHASE_MADE, async_session
        )
        marketing_svc = MarketingService(async_session)
        trigger_svc = TriggerService(marketing_svc)

        triggered_ids = await trigger_svc.check_triggers(
            "user_register", {"user_id": uid}, tenant_id=tenant_id
        )
        # No USER_REGISTER campaign exists for this tenant
        assert triggered_ids == []

    async def test_execute_trigger_success(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        campaign = await self._seed_campaign(
            tenant_id, uid, TriggerType.USER_REGISTER, async_session
        )
        marketing_svc = MarketingService(async_session)
        trigger_svc = TriggerService(marketing_svc)

        result = await trigger_svc.execute_trigger(campaign.id, [uid], tenant_id=tenant_id)
        assert result["success"] is True
        assert result["campaign_id"] == campaign.id
        assert result["sent_count"] == 1
        assert result["target_customer_count"] == 1

    async def test_execute_trigger_no_marketing_service(self, db_schema):
        trigger_svc = TriggerService(marketing_service=None)
        result = await trigger_svc.execute_trigger(999, [1])
        assert result["success"] is False
        assert "not configured" in result["message"]

    async def test_execute_trigger_campaign_not_found(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        marketing_svc = MarketingService(async_session)
        trigger_svc = TriggerService(marketing_svc)

        result = await trigger_svc.execute_trigger(99999, [uid], tenant_id=tenant_id)
        assert result["success"] is False
        assert "not found" in result["message"]
