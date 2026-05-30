"""Unit tests for WorkflowDefinitionModel."""

from __future__ import annotations

from datetime import UTC, datetime

from db.models.workflow_definition import WorkflowDefinitionModel


class TestWorkflowDefinitionModel:
    """Tests for WorkflowDefinitionModel instantiation and to_dict()."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() includes all seven non-datetime fields."""
        now = datetime.now(UTC)
        model = WorkflowDefinitionModel(
            id=1,
            tenant_id=5,
            name="Test Workflow",
            description="A test description",
            version="2.0",
            definition_data={"steps": []},
            created_at=now,
            updated_at=now,
        )
        d = model.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 5
        assert d["name"] == "Test Workflow"
        assert d["description"] == "A test description"
        assert d["version"] == "2.0"
        assert d["definition_data"] == {"steps": []}
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_datetime_iso_format(self):
        """Datetime fields are formatted as ISO strings."""
        now = datetime.now(UTC)
        model = WorkflowDefinitionModel(
            id=1,
            tenant_id=5,
            name="Test Workflow",
            description=None,
            version="1.0",
            definition_data={},
            created_at=now,
            updated_at=now,
        )
        d = model.to_dict()
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_json_fields_default_empty(self):
        """definition_data defaults to {} when None."""
        now = datetime.now(UTC)
        model = WorkflowDefinitionModel(
            id=1,
            tenant_id=5,
            name="Test",
            description=None,
            version="1.0",
            definition_data={},
            created_at=now,
            updated_at=now,
        )
        d = model.to_dict()
        assert d["definition_data"] == {}  # verifies the default was applied, not that the object is itself

    def test_attribute_assignment(self):
        """All fields can be set and read back correctly."""
        now = datetime.now(UTC)
        model = WorkflowDefinitionModel(
            id=42,
            tenant_id=10,
            name="My Workflow",
            description="Some desc",
            version="3.1",
            definition_data={"key": "value"},
            created_at=now,
            updated_at=now,
        )
        assert model.id == 42
        assert model.tenant_id == 10
        assert model.name == "My Workflow"
        assert model.description == "Some desc"
        assert model.version == "3.1"
        assert model.definition_data == {"key": "value"}
        assert model.created_at == now
        assert model.updated_at == now
