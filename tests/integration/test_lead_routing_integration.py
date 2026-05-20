"""Integration tests for lead routing — rule CRUD, auto-assignment, recycling, disqualify."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.customer_service import CustomerService
from services.lead_routing_service import LeadRoutingService
from services.user_service import UserService


async def _seed_user(async_session, tenant_id: int, role: str = "sales") -> int:
    """Create an active test user and return their id."""
    svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    user = await svc.create_user(
        username=f"routinguser_{suffix}",
        email=f"routing_{suffix}@example.com",
        password="Test@Pass1234",
        role=role,
        tenant_id=tenant_id,
    )
    # Set user to active so routing selects them
    user.status = "active"
    async_session.add(user)
    await async_session.flush()
    return user.id


# ──────────────────────────────────────────────────────────────────────────────────────
#  LeadRoutingService — rule matching and auto-assignment
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestLeadRoutingServiceIntegration:
    """Full lead routing lifecycle via the real DB."""

    async def test_evaluate_conditions_with_equals(self, db_schema, tenant_id, async_session):
        from models.routing import ConditionOperator, RuleCondition
        from services.lead_routing_service import evaluate_conditions

        cond = RuleCondition(field="region", operator=ConditionOperator.EQUALS, value="APAC")
        assert evaluate_conditions([cond], {"region": "APAC"}) is True
        assert evaluate_conditions([cond], {"region": "EMEA"}) is False

    async def test_evaluate_conditions_with_in(self, db_schema, tenant_id, async_session):
        from models.routing import ConditionOperator, RuleCondition
        from services.lead_routing_service import evaluate_conditions

        cond = RuleCondition(field="region", operator=ConditionOperator.IN, value=["APAC", "EMEA"])
        assert evaluate_conditions([cond], {"region": "APAC"}) is True
        assert evaluate_conditions([cond], {"region": "LATAM"}) is False

    async def test_get_sla_status(self, db_schema, tenant_id, async_session):
        from services.lead_routing_service import LeadRoutingService

        assert LeadRoutingService.get_sla_status(None) == "green"
        recent = LeadRoutingService.get_sla_status(datetime.now(UTC) - timedelta(hours=1))
        assert recent == "green"
        old = LeadRoutingService.get_sla_status(datetime.now(UTC) - timedelta(hours=25))
        assert old == "red"

    async def test_auto_assign_lead_no_rules_round_robin(self, db_schema, tenant_id, async_session):
        """Without any routing rules, a lead should still get a round-robin assignee."""
        uid = await _seed_user(async_session, tenant_id, role="sales")
        cust_svc = CustomerService(async_session)
        lead = await cust_svc.create_customer(
            {"name": "RoundRobin Lead", "status": "lead", "owner_id": 0},
            tenant_id=tenant_id,
        )
        routing_svc = LeadRoutingService(async_session)
        assigned_id = await routing_svc.auto_assign_lead(lead.id, tenant_id=tenant_id)
        # Should have selected the active sales user
        assert assigned_id == uid
        # Customer should be updated
        updated = await cust_svc.get_customer(lead.id, tenant_id=tenant_id)
        assert updated.owner_id == uid

    async def test_auto_assign_lead_with_matching_rule(self, db_schema, tenant_id, async_session):
        """With a matching rule, the lead should be assigned to the rule's assignee."""
        uid = await _seed_user(async_session, tenant_id, role="sales")
        from datetime import UTC, datetime
        from db.models.routing_rule import RoutingRuleModel

        rule = RoutingRuleModel(
            tenant_id=tenant_id,
            name="ACME Corp Rule",
            conditions_json=[{"field": "company", "operator": "equals", "value": "ACME Corp"}],
            assignee_type="user",
            assignee_id=uid,
            priority=100,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async_session.add(rule)
        await async_session.flush()

        cust_svc = CustomerService(async_session)
        lead = await cust_svc.create_customer(
            {"name": "ACME Lead", "status": "lead", "owner_id": 0, "company": "ACME Corp"},
            tenant_id=tenant_id,
        )
        routing_svc = LeadRoutingService(async_session)
        assigned_id = await routing_svc.auto_assign_lead(lead.id, tenant_id=tenant_id)
        assert assigned_id == uid

    async def test_inactive_rule_is_skipped(self, db_schema, tenant_id, async_session):
        """Inactive rules should be skipped during auto-assignment."""
        uid = await _seed_user(async_session, tenant_id, role="sales")
        from datetime import UTC, datetime
        from db.models.routing_rule import RoutingRuleModel

        rule = RoutingRuleModel(
            tenant_id=tenant_id,
            name="ACME Inactive Rule",
            conditions_json=[{"field": "company", "operator": "equals", "value": "ACME Corp"}],
            assignee_type="user",
            assignee_id=uid,
            priority=100,
            is_active=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async_session.add(rule)
        await async_session.flush()

        cust_svc = CustomerService(async_session)
        lead = await cust_svc.create_customer(
            {"name": "ACME Inactive Lead", "status": "lead", "owner_id": 0, "company": "ACME Corp"},
            tenant_id=tenant_id,
        )
        routing_svc = LeadRoutingService(async_session)
        # Should fall back to round-robin (lowest-load user)
        assigned_id = await routing_svc.auto_assign_lead(lead.id, tenant_id=tenant_id)
        assert assigned_id == uid

    async def test_reassign_lead_logs_history(self, db_schema, tenant_id, async_session):
        """Reassigning a lead should increment recycle_count and log history."""
        cust_svc = CustomerService(async_session)
        lead = await cust_svc.create_customer(
            {"name": "Reassign Test", "status": "lead", "owner_id": 1},
            tenant_id=tenant_id,
        )
        new_owner_id = await _seed_user(async_session, tenant_id)

        result = await cust_svc.reassign_lead(
            lead.id, new_owner_id, tenant_id=tenant_id, reason="wrong_owner"
        )
        assert result.owner_id == new_owner_id
        assert result.recycle_count == 1
        assert len(result.recycle_history) == 1
        assert result.recycle_history[0]["previous_owner_id"] == 1
        assert result.recycle_history[0]["reason"] == "wrong_owner"

    async def test_get_unassigned_leads(self, db_schema, tenant_id, async_session):
        """get_unassigned_leads should return only owner_id=0, status=lead.

        Note: create_customer auto-assigns leads (Step 8), so we bypass the
        service and insert directly to preserve unassigned state.
        """
        from db.models.customer import CustomerModel

        uid = await _seed_user(async_session, tenant_id)

        # Insert directly so owner_id=0 survives (avoids auto_assign_lead in create_customer)
        async_session.add(CustomerModel(
            tenant_id=tenant_id,
            name="Unassigned 1",
            status="lead",
            owner_id=0,
        ))
        async_session.add(CustomerModel(
            tenant_id=tenant_id,
            name="Assigned",
            status="lead",
            owner_id=uid,
        ))
        async_session.add(CustomerModel(
            tenant_id=tenant_id,
            name="Unassigned 2",
            status="lead",
            owner_id=0,
        ))
        await async_session.flush()

        items, total = await CustomerService(async_session).get_unassigned_leads(tenant_id=tenant_id)
        names = [c.name for c in items]
        assert "Unassigned 1" in names
        assert "Unassigned 2" in names
        assert "Assigned" not in names
        assert total == 2

    async def test_disqualify_overcycled_leads(self, db_schema, tenant_id, async_session):
        """Leads at max recycle count should be disqualified."""
        from db.models.customer import CustomerModel

        cust_svc = CustomerService(async_session)
        lead = CustomerModel(
            tenant_id=tenant_id,
            name="Overcycled",
            status="lead",
            owner_id=1,
            recycle_count=3,
            recycle_history=[],
        )
        async_session.add(lead)
        await async_session.flush()
        lead_id = lead.id

        routing_svc = LeadRoutingService(async_session)
        disqualified = await routing_svc.disqualify_overcycled_leads(tenant_id=tenant_id, max_recycle=3)
        assert lead_id in disqualified

        updated = await cust_svc.get_customer(lead_id, tenant_id=tenant_id)
        assert updated.status == "disqualified"

    async def test_recycle_stale_leads(self, db_schema, tenant_id, async_session):
        """Stale assigned leads should be recycled to pool."""
        uid = await _seed_user(async_session, tenant_id)
        from db.models.customer import CustomerModel

        # Create a stale lead (not awaiting - CustomerModel is a class, not coroutine)
        lead = CustomerModel(
            tenant_id=tenant_id,
            name="Stale Lead",
            status="lead",
            owner_id=uid,
            assigned_at=datetime.now(UTC) - timedelta(hours=48),
            recycle_count=0,
            recycle_history=[],
        )
        async_session.add(lead)
        await async_session.flush()
        lead_id = lead.id

        routing_svc = LeadRoutingService(async_session)
        recycled = await routing_svc.recycle_stale_leads(tenant_id=tenant_id, stale_hours=24, max_recycle=3)
        assert lead_id in recycled

        # Verify state after recycle
        await async_session.flush()
        check = await async_session.get(CustomerModel, lead_id)
        assert check.owner_id == 0
        assert check.recycle_count == 1
        assert len(check.recycle_history) == 1

    async def test_bulk_recycle(self, db_schema, tenant_id, async_session):
        """bulk_recycle should reset multiple leads at once."""
        cust_svc = CustomerService(async_session)
        uid = await _seed_user(async_session, tenant_id)

        lead1 = await cust_svc.create_customer(
            {"name": "Bulk 1", "status": "lead", "owner_id": uid},
            tenant_id=tenant_id,
        )
        lead2 = await cust_svc.create_customer(
            {"name": "Bulk 2", "status": "lead", "owner_id": uid},
            tenant_id=tenant_id,
        )

        recycled = await cust_svc.bulk_recycle([lead1.id, lead2.id], tenant_id=tenant_id)
        assert len(recycled) == 2

        c1 = await cust_svc.get_customer(lead1.id, tenant_id=tenant_id)
        assert c1.owner_id == 0
        assert c1.recycle_count == 1

    async def test_assign_owner_sets_assigned_at(self, db_schema, tenant_id, async_session):
        """assign_owner should set assigned_at on first assignment."""
        cust_svc = CustomerService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        lead = await cust_svc.create_customer(
            {"name": "Assign Test", "status": "lead", "owner_id": 0},
            tenant_id=tenant_id,
        )
        result = await cust_svc.assign_owner(lead.id, uid, tenant_id=tenant_id)
        assert result.owner_id == uid
        assert result.assigned_at is not None


# ──────────────────────────────────────────────────────────────────────────────────────
#  LeadRoutingService — get_matching_rule
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestRoutingRuleMatching:
    """Routing rule matching via the real DB."""

    async def test_highest_priority_rule_wins(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime
        from db.models.routing_rule import RoutingRuleModel

        for priority, name in [(50, "Low Priority"), (200, "High Priority")]:
            rule = RoutingRuleModel(
                tenant_id=tenant_id,
                name=name,
                conditions_json=[{"field": "region", "operator": "equals", "value": "APAC"}],
                assignee_type="user",
                assignee_id=1,
                priority=priority,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            async_session.add(rule)
        await async_session.flush()

        routing_svc = LeadRoutingService(async_session)
        rule = await routing_svc.get_matching_rule(tenant_id, {"region": "APAC"})
        assert rule is not None
        assert rule.name == "High Priority"

    async def test_no_matching_conditions_returns_none(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime
        from db.models.routing_rule import RoutingRuleModel

        rule = RoutingRuleModel(
            tenant_id=tenant_id,
            name="APAC Only",
            conditions_json=[{"field": "region", "operator": "in", "value": ["APAC"]}],
            assignee_type="user",
            assignee_id=1,
            priority=100,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async_session.add(rule)
        await async_session.flush()

        routing_svc = LeadRoutingService(async_session)
        result = await routing_svc.get_matching_rule(tenant_id, {"region": "EMEA"})
        assert result is None

    async def test_empty_conditions_matches_all_leads(self, db_schema, tenant_id, async_session):
        from datetime import UTC, datetime
        from db.models.routing_rule import RoutingRuleModel

        rule = RoutingRuleModel(
            tenant_id=tenant_id,
            name="Catch All",
            conditions_json=[],
            assignee_type="round_robin",
            assignee_id=None,
            priority=0,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async_session.add(rule)
        await async_session.flush()

        routing_svc = LeadRoutingService(async_session)
        result = await routing_svc.get_matching_rule(tenant_id, {"region": "ANYTHING"})
        assert result is not None
        assert result.name == "Catch All"