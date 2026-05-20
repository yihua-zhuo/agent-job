"""Unit tests for WorkflowModel."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from db.models.workflow import WorkflowExecutionModel, WorkflowModel


@pytest.fixture
def mock_db_session():
    """Minimal mock session for tests that don't require real DB."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.flush = MagicMock()
    session.refresh = MagicMock()
    session.execute = MagicMock()
    return session


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
        """conditions is [] when the field is None."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No conditions",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=None,
            status="draft",
            created_by=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.conditions is None
        assert workflow.to_dict()["conditions"] == []

    def test_actions_defaults_to_empty_list_when_none(self):
        """actions is [] when the field is None."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No actions",
            trigger_type="manual",
            trigger_config={},
            actions=None,
            conditions=None,
            status="draft",
            created_by=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.actions is None
        assert workflow.to_dict()["actions"] == []

    def test_trigger_config_defaults_to_empty_dict_when_none(self):
        """trigger_config is {} when the field is None."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="No config",
            trigger_type="manual",
            trigger_config=None,
            actions=[],
            conditions=[],
            status="draft",
            created_by=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.trigger_config is None
        assert workflow.to_dict()["trigger_config"] == {}

    def test_status_default_is_draft(self):
        """status serializes as 'draft' in to_dict() when unset."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Default status",
            trigger_type="manual",
            trigger_config={},
            actions=[],
            conditions=[],
            created_by=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert workflow.to_dict()["status"] == "draft"

    def test_trigger_type_default_serializes_as_manual(self):
        """trigger_type serializes as 'manual' in to_dict() when unset (server_default)."""
        workflow = WorkflowModel(
            id=1,
            tenant_id=1,
            name="Default trigger",
            trigger_config={},
            actions=[],
            conditions=[],
            status="draft",
            created_by=0,
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
            created_by=0,
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
            created_by=0,
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        assert isinstance(d["updated_at"], str)
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_with_minimal_fields(self):
        """to_dict works when only required fields are set."""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            id=5,
            tenant_id=99,
            name="Minimal",
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
        assert d["name"] == "Minimal"
        assert d["status"] == "draft"


class TestWorkflowExecutionModel:
    """Tests for WorkflowExecutionModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes execution fields."""
        now = datetime.now(UTC)
        execution = WorkflowExecutionModel(
            id=1,
            workflow_id=10,
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
        """to_dict works with minimal fields set."""
        now = datetime.now(UTC)
        execution = WorkflowExecutionModel(
            id=2,
            workflow_id=20,
            trigger_type="scheduled",
            triggered_by=0,
            started_at=now,
            completed_at=None,
            status="running",
            result=None,
        )
        d = execution.to_dict()
        assert d["id"] == 2
        assert d["workflow_id"] == 20
        assert d["status"] == "running"
