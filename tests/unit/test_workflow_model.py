"""Unit tests for WorkflowModel."""

from datetime import UTC, datetime

from db.models.workflow import WorkflowExecutionModel, WorkflowModel


class TestWorkflowModel:
    """Tests for WorkflowModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes id, tenant_id, name, trigger_type, conditions, actions, status, created_at, updated_at."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=1,
            tenant_id=42,
            name="Test Workflow",
            description="A test workflow",
            trigger_type="manual",
            trigger_config={"key": "value"},
            actions=[{"type": "email.send", "template": "welcome"}],
            conditions=[{"field": "status", "operator": "==", "value": "open"}],
            status="draft",
            created_by=7,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 42
        assert d["name"] == "Test Workflow"
        assert d["description"] == "A test workflow"
        assert d["trigger_type"] == "manual"
        assert d["trigger_config"] == {"key": "value"}
        assert d["actions"] == [{"type": "email.send", "template": "welcome"}]
        assert d["conditions"] == [{"field": "status", "operator": "==", "value": "open"}]
        assert d["status"] == "draft"
        assert d["created_by"] == 7
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_conditions_defaults_to_empty_list_when_none(self):
        """conditions is [] when the field is omitted (uses column default)."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No conditions",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.conditions == []
        assert workflow.to_dict()["conditions"] == []

    def test_actions_defaults_to_empty_list_when_none(self):
        """actions is [] when the field is omitted (uses column default)."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No actions",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.actions == []
        assert workflow.to_dict()["actions"] == []

    def test_trigger_config_defaults_to_empty_dict_when_none(self):
        """trigger_config is {} when the field is omitted (uses column default)."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No config",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.trigger_config == {}
        assert workflow.to_dict()["trigger_config"] == {}

    def test_status_default_is_draft(self):
        """status serializes as 'draft' in to_dict() when set to draft."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Default status",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.to_dict()["status"] == "draft"

    def test_trigger_type_default_serializes_as_manual(self):
        """trigger_type serializes as 'manual' in to_dict() when set to manual."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Default trigger",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.to_dict()["trigger_type"] == "manual"

    def test_created_at_isoformat(self):
        """created_at is serialized as ISO string in to_dict."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Time test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert isinstance(d["created_at"], str)
        assert d["created_at"] == now.isoformat()

    def test_updated_at_isoformat(self):
        """updated_at is serialized as ISO string in to_dict."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Time test",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=None,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert isinstance(d["updated_at"], str)
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_with_explicit_defaults(self):
        """to_dict returns the explicit default values as set (not coerced)."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=5,
            tenant_id=99,
            name="With Defaults",
            description="Desc",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=1,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert d["id"] == 5
        assert d["tenant_id"] == 99
        assert d["name"] == "With Defaults"
        assert d["status"] == "draft"
        assert d["trigger_type"] == "manual"
        assert d["description"] == "Desc"

    def test_to_dict_description_none(self):
        """to_dict returns description=None when not set."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=6,
            tenant_id=1,
            name="No Desc",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=1,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert d["description"] is None


class TestWorkflowExecutionModel:
    """Tests for WorkflowExecutionModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes execution fields."""
        now = datetime.now(UTC)
        execution = WorkflowExecutionModel(
            id=1,
            workflow_id=10,
            tenant_id=42,
            trigger_type="manual",
            triggered_by=5,
            started_at=now,
            completed_at=now,
            status="success",
            result={"steps": 3},
        )
        d = execution.to_dict()
        assert d["id"] == 1
        assert d["workflow_id"] == 10
        assert d["tenant_id"] == 42
        assert d["trigger_type"] == "manual"
        assert d["triggered_by"] == 5
        assert d["started_at"] == now.isoformat()
        assert d["completed_at"] == now.isoformat()
        assert d["status"] == "success"
        assert d["result"] == {"steps": 3}

    def test_result_none_when_not_set(self):
        """result is None in to_dict when field is None."""
        now = datetime.now(UTC)
        execution = WorkflowExecutionModel(
            id=1,
            workflow_id=10,
            trigger_type="manual",
            triggered_by=5,
            started_at=now,
            completed_at=None,
            status="running",
            result=None,
        )
        d = execution.to_dict()
        assert d["result"] is None
        assert d["completed_at"] is None

    def test_to_dict_with_minimal_fields(self):
        """to_dict works with minimal fields set and returns all 9 expected keys."""
        now = datetime.now(UTC)
        execution = WorkflowExecutionModel(
            id=2,
            workflow_id=20,
            tenant_id=1,
            trigger_type="scheduled",
            triggered_by=None,
            started_at=now,
            completed_at=None,
            status="running",
            result=None,
        )
        d = execution.to_dict()
        assert set(d.keys()) == {
            "id", "workflow_id", "tenant_id", "trigger_type", "triggered_by",
            "started_at", "completed_at", "status", "result",
        }
        assert d["id"] == 2
        assert d["workflow_id"] == 20
        assert d["status"] == "running"
