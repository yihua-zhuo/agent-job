"""Unit tests for lead routing Pydantic schemas and condition operators."""

import pytest
from pydantic import ValidationError

from models.routing import (
    ConditionOperator,
    LeadAssignPreview,
    RecycleHistoryEntry,
    RoutingRuleCreate,
    RoutingRuleUpdate,
    RoutingRulePriorityUpdate,
    RuleCondition,
    RuleTestRequest,
    LeadRecycleRequest,
)


class TestRuleCondition:
    def test_rejects_unsupported_field(self):
        with pytest.raises(ValidationError):
            RuleCondition(field="bad_field", operator="equals", value="x")

    def test_accepts_supported_fields(self):
        for field in ("region", "industry", "employee_count", "source", "created_date"):
            cond = RuleCondition(field=field, operator="equals", value="x")
            assert cond.field == field

    def test_all_operators_work(self):
        for op in ConditionOperator:
            cond = RuleCondition(field="region", operator=op, value="APAC")
            assert cond.operator == op


class TestRoutingRuleCreate:
    def test_default_values(self):
        rule = RoutingRuleCreate(name="Test Rule")
        assert rule.name == "Test Rule"
        assert rule.assignee_type == "round_robin"
        assert rule.is_active is True
        assert rule.conditions_json == []

    def test_rejects_invalid_assignee_type(self):
        with pytest.raises(ValidationError):
            RoutingRuleCreate(name="Bad", assignee_type="invalid")

    def test_accepts_valid_assignee_types(self):
        for at in ("user", "team", "round_robin"):
            rule = RoutingRuleCreate(name="Test", assignee_type=at)
            assert rule.assignee_type == at


class TestRoutingRuleUpdate:
    def test_all_fields_optional(self):
        update = RoutingRuleUpdate()
        assert update.name is None
        assert update.is_active is None

    def test_partial_update(self):
        update = RoutingRuleUpdate(priority=50, is_active=False)
        assert update.priority == 50
        assert update.is_active is False


class TestRoutingRulePriorityUpdate:
    def test_requires_rule_ids(self):
        with pytest.raises(ValidationError):
            RoutingRulePriorityUpdate(rule_ids=[])

    def test_valid_rule_ids(self):
        update = RoutingRulePriorityUpdate(rule_ids=[1, 2, 3])
        assert update.rule_ids == [1, 2, 3]


class TestLeadAssignPreview:
    def test_fields(self):
        preview = LeadAssignPreview(
            matched_rule_id=5,
            matched_rule_name="APAC Rule",
            assignee_id=3,
            assignee_type="user",
            sla_status="green",
        )
        assert preview.matched_rule_id == 5
        assert preview.assignee_id == 3
        assert preview.sla_status == "green"


class TestRuleTestRequest:
    def test_requires_conditions(self):
        with pytest.raises(ValidationError):
            RuleTestRequest(conditions=[], customer_data={})

    def test_valid_request(self):
        req = RuleTestRequest(
            conditions=[RuleCondition(field="region", operator="equals", value="APAC")],
            customer_data={"region": "APAC"},
        )
        assert len(req.conditions) == 1


class TestLeadRecycleRequest:
    def test_requires_customer_ids(self):
        with pytest.raises(ValidationError):
            LeadRecycleRequest(customer_ids=[])

    def test_valid_ids(self):
        req = LeadRecycleRequest(customer_ids=[1, 2, 3])
        assert req.customer_ids == [1, 2, 3]