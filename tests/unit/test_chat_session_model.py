"""Unit tests for ChatSessionModel construction and to_dict()."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from db.models import ChatSessionModel


class TestChatSessionModelToDict:
    """Tests for ChatSessionModel.to_dict() output."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() serializes id, tenant_id, user_id, title, created_at, updated_at."""
        now = datetime.now(UTC)
        session = MagicMock(spec=ChatSessionModel)
        session.id = 1
        session.tenant_id = 42
        session.user_id = 99
        session.title = "Test Chat"
        session.created_at = now
        session.updated_at = now

        result = ChatSessionModel.to_dict(session)

        assert result["id"] == 1
        assert result["tenant_id"] == 42
        assert result["user_id"] == 99
        assert result["title"] == "Test Chat"
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == now.isoformat()

    def test_to_dict_with_null_title(self):
        """title=None is serialized as None (not omitted)."""
        now = datetime.now(UTC)
        session = MagicMock(spec=ChatSessionModel)
        session.id = 2
        session.tenant_id = 1
        session.user_id = 5
        session.title = None
        session.created_at = now
        session.updated_at = now

        result = ChatSessionModel.to_dict(session)

        assert result["title"] is None

    def test_to_dict_with_null_created_at(self):
        """created_at=None is serialized as None."""
        session = MagicMock(spec=ChatSessionModel)
        session.id = 3
        session.tenant_id = 1
        session.user_id = 1
        session.title = "Chat"
        session.created_at = None
        session.updated_at = None

        result = ChatSessionModel.to_dict(session)

        assert result["created_at"] is None
        assert result["updated_at"] is None
