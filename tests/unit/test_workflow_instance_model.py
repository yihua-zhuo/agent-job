"""Unit tests for WorkflowInstanceModel."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
        assert d["id"] == 1
        assert d["tenant_id"] == 5
        assert d["definition_id"] == 10
        assert d["status"] == "pending"
        assert d["context"] == {"vars": {}}
        assert d["started_at"] == now.isoformat()
        assert d["completed_at"] is None

    def test_to_dict_datetime_iso_format(self):
        """Datetime fields are formatted as ISO strings."""
        now = datetime.now(UTC)
        later = now + timedelta(seconds=1)
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
        assert d["started_at"] != d["completed_at"]

    def test_to_dict_context_defaults_to_empty_when_none(self):
        """context defaults to {} when None is passed to constructor."""
        now = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            status="pending",
            context=None,
            started_at=now,
            completed_at=None,
        )
        d = model.to_dict()
        assert d["context"] == {}  # exercises the or-{} fallback

    def test_to_dict_context_preserved_when_provided(self):
        """context is returned unchanged when explicitly set to a non-None value."""
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
        assert d["context"] == {"vars": {}}

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
        """Default status is 'pending' when not provided."""
        now = datetime.now(UTC)
        model = WorkflowInstanceModel(
            id=1,
            tenant_id=5,
            definition_id=10,
            context={},
            started_at=now,
        )
        assert model.status == "pending"
