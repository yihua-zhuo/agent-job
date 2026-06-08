"""Unit tests for WorkflowModel.

Note: constraint enforcement for nullable=False fields (tenant_id, name,
trigger_type) is exercised by integration tests against a real DB.
At the Python level, SQLAlchemy constructs instances lazily without
validating non-null fields; a missing required field will only fail
at flush time. See tests/integration/test_workflow_model_integration.py
for constraint coverage.
"""

from datetime import UTC, datetime

import pytest

from db.models.workflow import WorkflowExecutionModel, WorkflowModel, WorkflowNodeModel


def _now() -> datetime:
    return datetime.now(UTC)


def make_workflow(**overrides) -> WorkflowModel:
    """Build a WorkflowModel with sensible defaults; override any field by kwarg."""
    now = _now()
    defaults = {
        "id": 1,
        "tenant_id": 42,
        "name": "Test Workflow",
        "description": "A test workflow",
        "trigger_type": "manual",
        "trigger_config": {"key": "value"},
        "actions": [{"type": "email.send", "template": "welcome"}],
        "conditions": [{"field": "status", "operator": "==", "value": "open"}],
        "status": "draft",
        "created_by": 7,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return WorkflowModel(**defaults)


def make_execution(**overrides) -> WorkflowExecutionModel:
    """Build a WorkflowExecutionModel with sensible defaults; override any field by kwarg."""
    now = _now()
    defaults = {
        "id": 1,
        "workflow_id": 10,
        "tenant_id": 42,
        "trigger_type": "manual",
        "triggered_by": 5,
        "started_at": now,
        "completed_at": now,
        "status": "success",
        "result": {"steps": 3},
    }
    defaults.update(overrides)
    return WorkflowExecutionModel(**defaults)


def make_node(**overrides) -> WorkflowNodeModel:
    """Build a WorkflowNodeModel with sensible defaults; override any field by kwarg."""
    now = _now()
    defaults = {
        "id": 1,
        "workflow_id": 10,
        "tenant_id": 42,
        "node_type": "action",
        "definition_json": {"action": "send_email"},
        "input": {"to": "user@example.com"},
        "output": {"sent": True},
        "status": "completed",
        "execution_order": 1,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return WorkflowNodeModel(**defaults)


class TestWorkflowModel:
    """Tests for WorkflowModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes the complete set of expected keys and correct values."""
        now = _now()
        workflow = make_workflow(created_at=now, updated_at=now)
        d = workflow.to_dict()

        # Key completeness — protects against accidental key drops or additions.
        assert set(d.keys()) == {
            "id",
            "tenant_id",
            "name",
            "description",
            "trigger_type",
            "trigger_config",
            "actions",
            "conditions",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        }

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

    @pytest.mark.parametrize(
        "field,serialized",
        [
            ("conditions", []),
            ("actions", []),
            ("trigger_config", {}),
        ],
    )
    def test_default_serialization_for_jsonb_fields(self, field, serialized):
        """to_dict() serializes empty list/dict defaults correctly for JSONB fields."""
        workflow = make_workflow(conditions=[], actions=[], trigger_config={})
        assert workflow.to_dict()[field] == serialized

    def test_to_dict_description_none(self):
        """to_dict returns description=None when not set."""
        workflow = make_workflow(id=6, description=None)
        d = workflow.to_dict()
        assert d["description"] is None

    def test_to_dict_created_at_none(self):
        """to_dict returns created_at=None when the field is None."""
        workflow = make_workflow(id=7, created_at=None, updated_at=None)
        d = workflow.to_dict()
        assert d["created_at"] is None
        assert d["updated_at"] is None


class TestWorkflowExecutionModel:
    """Tests for WorkflowExecutionModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes the complete set of expected keys and correct values."""
        now = _now()
        execution = make_execution(started_at=now, completed_at=now)
        d = execution.to_dict()

        assert set(d.keys()) == {
            "id",
            "workflow_id",
            "tenant_id",
            "trigger_type",
            "triggered_by",
            "started_at",
            "completed_at",
            "status",
            "result",
        }

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
        execution = make_execution(completed_at=None, result=None, status="running")
        d = execution.to_dict()
        assert d["result"] is None
        assert d["completed_at"] is None

    def test_to_dict_with_none_optional_fields(self):
        """to_dict works with optional fields set to None and returns all 9 expected keys."""
        execution = make_execution(
            id=2,
            workflow_id=20,
            triggered_by=None,
            completed_at=None,
            status="running",
            result=None,
        )
        d = execution.to_dict()
        assert set(d.keys()) == {
            "id",
            "workflow_id",
            "tenant_id",
            "trigger_type",
            "triggered_by",
            "started_at",
            "completed_at",
            "status",
            "result",
        }
        assert d["id"] == 2
        assert d["workflow_id"] == 20
        assert d["status"] == "running"


class TestWorkflowNodeModel:
    """Tests for WorkflowNodeModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes the complete set of expected keys and correct values."""
        now = _now()
        node = make_node(created_at=now, updated_at=now)
        d = node.to_dict()

        assert set(d.keys()) == {
            "id",
            "workflow_id",
            "tenant_id",
            "node_type",
            "definition_json",
            "input",
            "output",
            "status",
            "execution_order",
            "created_at",
            "updated_at",
        }

        assert d["id"] == 1
        assert d["workflow_id"] == 10
        assert d["tenant_id"] == 42
        assert d["node_type"] == "action"
        assert d["definition_json"] == {"action": "send_email"}
        assert d["input"] == {"to": "user@example.com"}
        assert d["output"] == {"sent": True}
        assert d["status"] == "completed"
        assert d["execution_order"] == 1
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_output_none(self):
        """to_dict returns output=None when not set."""
        node = make_node(
            id=2,
            node_type="condition",
            definition_json={},
            input={},
            output=None,
            status="pending",
            execution_order=0,
        )
        d = node.to_dict()
        assert d["output"] is None
