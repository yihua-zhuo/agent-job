"""Unit tests for AutomationRuleModel and AutomationLogModel ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

from db.models.automation_log import AutomationLogModel
from db.models.automation_rule import AutomationRuleModel


class TestAutomationRuleModelToDict:
    """Test AutomationRuleModel.to_dict() serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict returns all fields including tenant_id, name, trigger_event, conditions, actions."""
        now = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
        rule = AutomationRuleModel(
            id=1,
            tenant_id=5,
            name="Welcome Email",
            description="Send welcome on signup",
            trigger_event="user.signup",
            conditions=[{"field": "plan", "op": "eq", "value": "free"}],
            actions=[{"type": "send_email", "template": "welcome"}],
            enabled=True,
            created_by=2,
            created_at=now,
            updated_at=now,
        )
        d = rule.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 5
        assert d["name"] == "Welcome Email"
        assert d["description"] == "Send welcome on signup"
        assert d["trigger_event"] == "user.signup"
        assert d["conditions"] == [{"field": "plan", "op": "eq", "value": "free"}]
        assert d["actions"] == [{"type": "send_email", "template": "welcome"}]
        assert d["enabled"] is True
        assert d["created_by"] == 2
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_serializes_datetime_as_iso_string(self):
        """Datetime fields are serialized as ISO 8601 strings."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        rule = AutomationRuleModel(
            id=2,
            tenant_id=1,
            name="Test",
            trigger_event="deal.created",
            created_at=now,
            updated_at=now,
        )
        d = rule.to_dict()
        assert d["created_at"] == "2024-01-01T12:00:00+00:00"
        assert d["updated_at"] == "2024-01-01T12:00:00+00:00"

    def test_to_dict_handles_none_datetime(self):
        """None datetime fields return None from isoformat guard."""
        rule = AutomationRuleModel(
            id=3,
            tenant_id=1,
            name="Test",
            trigger_event="deal.created",
        )
        d = rule.to_dict()
        assert d["created_at"] is None
        assert d["updated_at"] is None

    def test_to_dict_handles_empty_conditions_and_actions(self):
        """conditions and actions default to [] when falsy."""
        rule = AutomationRuleModel(
            id=4,
            tenant_id=1,
            name="Test",
            trigger_event="deal.created",
        )
        d = rule.to_dict()
        assert d["conditions"] == []
        assert d["actions"] == []


class TestAutomationRuleModelDefaults:
    """Test AutomationRuleModel column default values."""

    def test_enabled_column_default_is_true(self):
        """The enabled column defaults to True."""
        col = AutomationRuleModel.__table__.c.enabled
        assert col.default is not None and col.default.arg is True

    def test_conditions_column_has_callable_default(self):
        """The conditions column has a callable default (empty list factory)."""
        col = AutomationRuleModel.__table__.c.conditions
        assert col.default is not None
        assert callable(col.default.arg)

    def test_actions_column_has_callable_default(self):
        """The actions column has a callable default (empty list factory)."""
        col = AutomationRuleModel.__table__.c.actions
        assert col.default is not None
        assert callable(col.default.arg)

    def test_created_by_column_default_is_zero(self):
        """The created_by column defaults to 0."""
        col = AutomationRuleModel.__table__.c.created_by
        assert col.default is not None and col.default.arg == 0


class TestAutomationLogModelToDict:
    """Test AutomationLogModel.to_dict() serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict returns all fields including nested JSON and datetime."""
        now = datetime(2024, 7, 20, 14, 0, 0, tzinfo=UTC)
        log = AutomationLogModel(
            id=1,
            rule_id=10,
            tenant_id=5,
            trigger_event="user.signup",
            trigger_context={"user_id": 42, "email": "a@b.com"},
            actions_executed=[{"type": "send_email", "sent": True}],
            status="success",
            error_message=None,
            executed_by=1,
            executed_at=now,
        )
        d = log.to_dict()
        assert d["id"] == 1
        assert d["rule_id"] == 10
        assert d["tenant_id"] == 5
        assert d["trigger_event"] == "user.signup"
        assert d["trigger_context"] == {"user_id": 42, "email": "a@b.com"}
        assert d["actions_executed"] == [{"type": "send_email", "sent": True}]
        assert d["status"] == "success"
        assert d["error_message"] is None
        assert d["executed_by"] == 1
        assert d["executed_at"] == now.isoformat()

    def test_to_dict_serializes_datetime_as_iso_string(self):
        """executed_at is serialized as an ISO 8601 string."""
        now = datetime(2024, 3, 10, 8, 45, 0, tzinfo=UTC)
        log = AutomationLogModel(
            id=2,
            rule_id=1,
            tenant_id=1,
            trigger_event="x",
            executed_at=now,
        )
        d = log.to_dict()
        assert d["executed_at"] == "2024-03-10T08:45:00+00:00"

    def test_to_dict_handles_none_executed_at(self):
        """None executed_at returns None from isoformat guard."""
        log = AutomationLogModel(
            id=3,
            rule_id=1,
            tenant_id=1,
            trigger_event="x",
        )
        d = log.to_dict()
        assert d["executed_at"] is None

    def test_to_dict_handles_empty_trigger_context(self):
        """trigger_context defaults to {} when falsy."""
        log = AutomationLogModel(
            id=4,
            rule_id=1,
            tenant_id=1,
            trigger_event="x",
        )
        d = log.to_dict()
        assert d["trigger_context"] == {}

    def test_to_dict_handles_empty_actions_executed(self):
        """actions_executed defaults to [] when falsy."""
        log = AutomationLogModel(
            id=5,
            rule_id=1,
            tenant_id=1,
            trigger_event="x",
        )
        d = log.to_dict()
        assert d["actions_executed"] == []


class TestAutomationLogModelDefaults:
    """Test AutomationLogModel column default values."""

    def test_status_column_default_is_success(self):
        """The status column defaults to 'success'."""
        col = AutomationLogModel.__table__.c.status
        assert col.default is not None and col.default.arg == "success"

    def test_trigger_context_column_has_callable_default(self):
        """The trigger_context column has a callable default (empty dict factory)."""
        col = AutomationLogModel.__table__.c.trigger_context
        assert col.default is not None
        assert callable(col.default.arg)

    def test_actions_executed_column_has_callable_default(self):
        """The actions_executed column has a callable default (empty list factory)."""
        col = AutomationLogModel.__table__.c.actions_executed
        assert col.default is not None
        assert callable(col.default.arg)

    def test_executed_by_column_default_is_zero(self):
        """The executed_by column defaults to 0."""
        col = AutomationLogModel.__table__.c.executed_by
        assert col.default is not None and col.default.arg == 0


class TestAutomationModelsIndexing:
    """Test that tenant_id and other key columns are indexed."""

    def test_rule_tenant_id_is_indexed(self):
        """AutomationRuleModel.tenant_id column is indexed."""
        col = AutomationRuleModel.__table__.c.tenant_id
        assert col.index is True

    def test_log_tenant_id_is_indexed(self):
        """AutomationLogModel.tenant_id column is indexed."""
        col = AutomationLogModel.__table__.c.tenant_id
        assert col.index is True

    def test_rule_trigger_event_is_indexed(self):
        """AutomationRuleModel.trigger_event column is indexed."""
        col = AutomationRuleModel.__table__.c.trigger_event
        assert col.index is True

    def test_log_rule_id_is_indexed(self):
        """AutomationLogModel.rule_id column is indexed."""
        col = AutomationLogModel.__table__.c.rule_id
        assert col.index is True
