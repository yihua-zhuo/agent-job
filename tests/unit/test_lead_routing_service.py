"""Unit tests for src/services/lead_routing_service.py — rule matching, load balancing, SLA, recycling."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.lead_routing_service import (
    LeadRoutingService,
    evaluate_conditions,
)
from models.routing import ConditionOperator, RuleCondition


# ---------------------------------------------------------------------------
# evaluate_conditions (synchronous)
# ---------------------------------------------------------------------------

class TestEvaluateConditions:
    def _cond(self, field, operator, value):
        return RuleCondition(field=field, operator=operator, value=value)

    def _cust(self, **kwargs):
        return kwargs

    def test_equals_match(self):
        cond = self._cond("region", ConditionOperator.EQUALS, "APAC")
        assert evaluate_conditions([cond], self._cust(region="APAC")) is True
        assert evaluate_conditions([cond], self._cust(region="EMEA")) is False

    def test_not_equals_match(self):
        cond = self._cond("region", ConditionOperator.NOT_EQUALS, "APAC")
        assert evaluate_conditions([cond], self._cust(region="EMEA")) is True
        assert evaluate_conditions([cond], self._cust(region="APAC")) is False

    def test_in_match(self):
        cond = self._cond("region", ConditionOperator.IN, ["APAC", "EMEA"])
        assert evaluate_conditions([cond], self._cust(region="APAC")) is True
        assert evaluate_conditions([cond], self._cust(region="LATAM")) is False

    def test_not_in_match(self):
        cond = self._cond("region", ConditionOperator.NOT_IN, ["APAC", "EMEA"])
        assert evaluate_conditions([cond], self._cust(region="LATAM")) is True
        assert evaluate_conditions([cond], self._cust(region="APAC")) is False

    def test_gt_match(self):
        cond = self._cond("employee_count", ConditionOperator.GT, 100)
        assert evaluate_conditions([cond], self._cust(employee_count=200)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=50)) is False
        assert evaluate_conditions([cond], self._cust(employee_count=100)) is False

    def test_lt_match(self):
        cond = self._cond("employee_count", ConditionOperator.LT, 50)
        assert evaluate_conditions([cond], self._cust(employee_count=10)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=100)) is False

    def test_gte_match(self):
        cond = self._cond("employee_count", ConditionOperator.GTE, 100)
        assert evaluate_conditions([cond], self._cust(employee_count=100)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=200)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=50)) is False

    def test_lte_match(self):
        cond = self._cond("employee_count", ConditionOperator.LTE, 100)
        assert evaluate_conditions([cond], self._cust(employee_count=100)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=50)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=200)) is False

    def test_between_match(self):
        cond = self._cond("employee_count", ConditionOperator.BETWEEN, [10, 100])
        assert evaluate_conditions([cond], self._cust(employee_count=50)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=10)) is True
        assert evaluate_conditions([cond], self._cust(employee_count=5)) is False
        assert evaluate_conditions([cond], self._cust(employee_count=200)) is False

    def test_missing_field_returns_false(self):
        cond = self._cond("region", ConditionOperator.EQUALS, "APAC")
        assert evaluate_conditions([cond], self._cust()) is False

    def test_multiple_conditions_all_must_match(self):
        cond1 = self._cond("region", ConditionOperator.EQUALS, "APAC")
        cond2 = self._cond("industry", ConditionOperator.EQUALS, "tech")
        assert evaluate_conditions([cond1, cond2], self._cust(region="APAC", industry="tech")) is True
        assert evaluate_conditions([cond1, cond2], self._cust(region="APAC", industry="finance")) is False

    def test_empty_conditions_list_matches_all(self):
        assert evaluate_conditions([], self._cust(region="ANY")) is True


# ---------------------------------------------------------------------------
# get_sla_status (static, synchronous)
# ---------------------------------------------------------------------------

class TestSlaStatus:
    def test_none_returns_green(self):
        assert LeadRoutingService.get_sla_status(None) == "green"

    def test_very_recent_returns_green(self):
        recent = datetime.now(UTC) - timedelta(minutes=30)
        assert LeadRoutingService.get_sla_status(recent) == "green"

    def test_12_hours_returns_yellow(self):
        half_day = datetime.now(UTC) - timedelta(hours=12)
        assert LeadRoutingService.get_sla_status(half_day) == "yellow"

    def test_just_under_2_hours_returns_green(self):
        almost_2_hrs = datetime.now(UTC) - timedelta(hours=1, minutes=59)
        assert LeadRoutingService.get_sla_status(almost_2_hrs) == "green"

    def test_25_hours_returns_red(self):
        over_day = datetime.now(UTC) - timedelta(hours=25)
        assert LeadRoutingService.get_sla_status(over_day) == "red"


# ---------------------------------------------------------------------------
# ConditionOperator enum values
# ---------------------------------------------------------------------------

class TestConditionOperator:
    def test_all_operators_exist(self):
        assert ConditionOperator.EQUALS.value == "equals"
        assert ConditionOperator.NOT_EQUALS.value == "not_equals"
        assert ConditionOperator.IN.value == "in"
        assert ConditionOperator.NOT_IN.value == "not_in"
        assert ConditionOperator.GT.value == "gt"
        assert ConditionOperator.LT.value == "lt"
        assert ConditionOperator.GTE.value == "gte"
        assert ConditionOperator.LTE.value == "lte"
        assert ConditionOperator.BETWEEN.value == "between"


# ---------------------------------------------------------------------------
# RuleCondition validation
# ---------------------------------------------------------------------------

class TestRuleCondition:
    def test_rejects_unsupported_field(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RuleCondition(field="unsupported", operator="equals", value="x")

    def test_accepts_supported_fields(self):
        for field in ("region", "industry", "employee_count", "source", "created_date"):
            cond = RuleCondition(field=field, operator="equals", value="x")
            assert cond.field == field

    def test_all_operators_work(self):
        for op in ConditionOperator:
            cond = RuleCondition(field="region", operator=op, value="APAC")
            assert cond.operator == op