"""Unit tests for WorkflowInstanceModel."""

from __future__ import annotations

from datetime import UTC, datetime

from db.models.workflow_instance import WorkflowInstanceModel


class TestWorkflowInstanceModel:
    """Tests for WorkflowInstanceModel instantiation and to_dict()."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() includes all expected fields."""
        now = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            status="pending",
            context={"vars": {}},
            started_at=now,
            completed_at=None,
        )
        d = model.to_dict()
        assert "id" in d
        assert "tenant_id" in d
        assert "definition_id" in d
        assert "status" in d
        assert "context" in d
        assert "started_at" in d
        assert "completed_at" in d

    def test_to_dict_datetime_iso_format(self):
        """Datetime fields are formatted as ISO strings."""
        now = datetime.now(UTC)
        later = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            status="running",
            context={},
            started_at=now,
            completed_at=later,
        )
        d = model.to_dict()
        assert d["started_at"] == now.isoformat()
        assert d["completed_at"] == later.isoformat()

    def test_to_dict_json_fields_default_empty(self):
        """context defaults to {} when None."""
        now = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            status="pending",
            context=None,  # type: ignore
            started_at=now,
            completed_at=None,
        )
        d = model.to_dict()
        assert d["context"] == {}

    def test_attribute_assignment(self):
        """All fields can be set and read back correctly."""
        now = datetime.now(UTC)
        later = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=99,
            tenant_id=7,
            definition_id=3,
            status="failed",
            context={"error": "oops"},
            started_at=now,
            completed_at=later,
        )
        assert model.id == 99
        assert model.tenant_id == 7
        assert model.definition_id == 3
        assert model.status == "failed"
        assert model.context == {"error": "oops"}
        assert model.started_at == now
        assert model.completed_at == later

    def test_default_status_is_pending(self):
        """Default status is 'pending' when not specified."""
        now = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            status="pending",
            context={},
            started_at=now,
            completed_at=None,
        )
        assert model.status == "pending"
