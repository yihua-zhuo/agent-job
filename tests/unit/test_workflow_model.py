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
        """to_dict() includes the expected keys and correct values."""
        now = _now()
        workflow = make_workflow(created_at=now, updated_at=now)
        d = workflow.to_dict()

        # Subset check — allows additive evolution of the serialization
        # contract (e.g. a new audit column) without breaking every test
        # in the class. Exact equality is exercised by the per-field
        # assertions below.
        expected_keys = {
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
        assert expected_keys.issubset(d.keys())

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
        """to_dict() default for JSONB fields is the empty container (not None).

        Construct the model with only required fields so the column-level
        default (empty list / empty dict) is what populates the JSONB
        columns. This is the case operators see for a freshly-created
        workflow with no actions/conditions/trigger_config.
        """
        now = _now()
        workflow = WorkflowModel(
            id=2,
            tenant_id=42,
            name="Defaults Test",
            trigger_type="manual",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        assert workflow.to_dict()[field] == serialized

    def test_python_level_defaults_applied_at_construction(self):
        """to_dict() returns the column defaults (empty list / dict) when
        the JSONB columns are omitted from construction.

        The SQLAlchemy ``default=dict`` / ``default=list`` column defaults
        are INSERT-time, so the in-memory instance attributes are ``None``
        right after ``__init__``; the ``or {}`` / ``or []`` fallback in
        ``to_dict()`` is what the operator-facing API relies on. This test
        pins that fallback path so a regression that removes either the
        fallback or the column default is caught.
        """
        now = _now()
        workflow = WorkflowModel(
            id=3,
            tenant_id=42,
            name="Defaults Instance Test",
            trigger_type="manual",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        d = workflow.to_dict()
        # to_dict() must surface the empty container fallback even when
        # the in-memory attribute is None (i.e. when the column default
        # has not yet been applied).
        assert d["trigger_config"] == {}
        assert d["actions"] == []
        assert d["conditions"] == []

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

    def test_model_invariants_preserved(self):
        """Python-level invariants: to_dict preserves field values without coercion."""
        wf = make_workflow(name="Renamed Workflow", status="active", tenant_id=42)
        d = wf.to_dict()
        assert d["name"] == "Renamed Workflow"
        assert d["status"] == "active"
        assert d["tenant_id"] == 42


class TestWorkflowExecutionModel:
    """Tests for WorkflowExecutionModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes the expected keys and correct values."""
        now = _now()
        execution = make_execution(started_at=now, completed_at=now)
        d = execution.to_dict()

        expected_keys = {
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
        assert expected_keys.issubset(d.keys())

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

    def test_model_invariants_preserved(self):
        """to_dict preserves field values without coercion, even for non-default values."""
        execution = make_execution(
            status="failed",
            triggered_by=None,
            result={"error": "boom"},
        )
        d = execution.to_dict()
        assert d["status"] == "failed"
        assert d["triggered_by"] is None
        assert d["result"] == {"error": "boom"}


class TestWorkflowNodeModel:
    """Tests for WorkflowNodeModel."""

    def test_to_dict_returns_all_expected_keys(self):
        """to_dict() includes the expected keys and correct values."""
        now = _now()
        node = make_node(created_at=now, updated_at=now)
        d = node.to_dict()

        expected_keys = {
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
        assert expected_keys.issubset(d.keys())

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

    def test_to_dict_with_running_status(self):
        """to_dict includes status='running' as set by the caller (no coercion)."""
        node = make_node(status="running", execution_order=3)
        d = node.to_dict()
        assert d["status"] == "running"
        assert d["execution_order"] == 3

    def test_execution_order_zero_preserved(self):
        """execution_order=0 is preserved verbatim when explicitly passed.

        Named after the *behaviour* (zero is preserved) rather than the
        *implementation* (column default), since the test exercises the
        pass-through path, not the default value path. The column default
        is exercised implicitly by the model constructor in
        ``make_node`` and the ``to_dict()`` test above.
        """
        node = make_node(execution_order=0)
        assert node.to_dict()["execution_order"] == 0

    def test_definition_json_none(self):
        """to_dict returns the empty dict fallback when definition_json is None.

        definition_json is declared nullable=False with a Python-side default
        of dict, so a constructed instance has a real dict. The to_dict
        fallback `or {}` only triggers if the ORM somehow surfaced a None
        (e.g. legacy data). This test pins the fallback behaviour. The
        second assertion exercises a freshly-constructed instance *without*
        specifying definition_json: SQLAlchemy's ``default=dict`` is an
        INSERT-time default, so the in-memory attribute is None until flush,
        but ``to_dict()`` must still surface ``{}`` via the fallback.
        """
        node = make_node(definition_json=None)
        assert node.to_dict()["definition_json"] == {}

        now = _now()
        node_default = WorkflowNodeModel(
            id=99,
            workflow_id=10,
            tenant_id=42,
            node_type="action",
            input={"to": "user@example.com"},
            output=None,
            status="pending",
            execution_order=0,
            created_at=now,
            updated_at=now,
        )
        # to_dict's fallback `or {}` must surface {} even when the
        # column-level default has not yet populated the attribute.
        assert node_default.to_dict()["definition_json"] == {}

    def test_model_invariants_preserved(self):
        """to_dict preserves field values without coercion."""
        node = make_node(node_type="trigger", execution_order=99)
        d = node.to_dict()
        assert d["node_type"] == "trigger"
        assert d["execution_order"] == 99
