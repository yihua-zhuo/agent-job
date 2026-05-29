"""Unit tests for ChatMessageModel construction and to_dict()."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from db.models import ChatMessageModel


class TestChatMessageModelToDict:
    """Tests for ChatMessageModel.to_dict() output."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() serializes id, session_id, tenant_id, role, content, intent, created_at."""
        now = datetime.now(UTC)
        msg = MagicMock(spec=ChatMessageModel)
        msg.id = 1
        msg.session_id = 10
        msg.tenant_id = 42
        msg.role = "user"
        msg.content = "Hello"
        msg.intent = "greeting"
        msg.created_at = now

        result = ChatMessageModel.to_dict(msg)

        assert result["id"] == 1
        assert result["session_id"] == 10
        assert result["tenant_id"] == 42
        assert result["role"] == "user"
        assert result["content"] == "Hello"
        assert result["intent"] == "greeting"
        assert result["created_at"] == now.isoformat()

    def test_to_dict_with_null_intent(self):
        """intent=None is serialized as None."""
        now = datetime.now(UTC)
        msg = MagicMock(spec=ChatMessageModel)
        msg.id = 2
        msg.session_id = 1
        msg.tenant_id = 1
        msg.role = "assistant"
        msg.content = "Hi there!"
        msg.intent = None
        msg.created_at = now

        result = ChatMessageModel.to_dict(msg)

        assert result["intent"] is None
        assert result["content"] == "Hi there!"

    def test_to_dict_with_null_created_at(self):
        """created_at=None is serialized as None."""
        msg = MagicMock(spec=ChatMessageModel)
        msg.id = 3
        msg.session_id = 1
        msg.tenant_id = 1
        msg.role = "user"
        msg.content = "Test"
        msg.intent = None
        msg.created_at = None

        result = ChatMessageModel.to_dict(msg)

        assert result["created_at"] is None

    def test_to_dict_role_assistant(self):
        """role='assistant' is preserved."""
        now = datetime.now(UTC)
        msg = MagicMock(spec=ChatMessageModel)
        msg.id = 4
        msg.session_id = 1
        msg.tenant_id = 1
        msg.role = "assistant"
        msg.content = "How can I help?"
        msg.intent = "support"
        msg.created_at = now

        result = ChatMessageModel.to_dict(msg)

        assert result["role"] == "assistant"
