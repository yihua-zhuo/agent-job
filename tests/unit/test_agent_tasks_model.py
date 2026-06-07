"""Unit tests for src/db/models/agent_tasks.py — AgentTaskModel ORM class."""

import types
from unittest.mock import MagicMock

from db.models.agent_tasks import AgentTaskModel, AgentTaskStatus


class TestAgentTaskStatus:
    def test_enum_has_five_values(self):
        values = {getattr(AgentTaskStatus, name) for name in dir(AgentTaskStatus) if not name.startswith("_")}
        assert len(values) >= 5
        assert "pending" in values
        assert "dispatched" in values
        assert "running" in values
        assert "completed" in values
        assert "failed" in values


class TestAgentTaskModel:
    def test_tablename(self):
        assert AgentTaskModel.__tablename__ == "agent_tasks"

    def test_has_id_column(self):
        assert hasattr(AgentTaskModel, "id")

    def test_has_task_id_column(self):
        assert hasattr(AgentTaskModel, "task_id")

    def test_has_tenant_id_column(self):
        assert hasattr(AgentTaskModel, "tenant_id")

    def test_has_description_column(self):
        assert hasattr(AgentTaskModel, "description")

    def test_has_status_column(self):
        assert hasattr(AgentTaskModel, "status")

    def test_has_subtasks_column(self):
        assert hasattr(AgentTaskModel, "subtasks")

    def test_has_created_at_column(self):
        assert hasattr(AgentTaskModel, "created_at")

    def test_has_updated_at_column(self):
        assert hasattr(AgentTaskModel, "updated_at")


class TestCompositeIndex:
    def test_composite_index_present(self):
        table_args = AgentTaskModel.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "ix_agent_tasks_task_id_tenant_id" in index_names


def _make_mock_model():
    mock_instance = MagicMock(spec=AgentTaskModel)
    mock_instance.id = 1
    mock_instance.task_id = "atask_abc123"
    mock_instance.tenant_id = 42
    mock_instance.description = "Test description"
    mock_instance.status = "pending"
    mock_instance.subtasks = []
    mock_instance.created_at = None
    mock_instance.updated_at = None

    def to_dict_method(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "description": self.description,
            "status": self.status,
            "subtasks": self.subtasks or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    mock_instance.to_dict = types.MethodType(to_dict_method, mock_instance)
    return mock_instance


class TestToDict:
    def test_to_dict_returns_all_columns(self):
        """to_dict() includes a key for every column."""
        assert hasattr(AgentTaskModel, "to_dict")
        mock_instance = _make_mock_model()
        d = mock_instance.to_dict()
        assert "id" in d
        assert "task_id" in d
        assert "tenant_id" in d
        assert "description" in d
        assert "status" in d
        assert "subtasks" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_to_dict_handles_none_subtasks(self):
        """to_dict() handles a model instance with subtasks=None gracefully."""
        mock_instance = _make_mock_model()
        mock_instance.subtasks = None
        d = mock_instance.to_dict()
        assert d["subtasks"] == []
