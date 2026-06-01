"""
Integration tests for ChatSessionModel and ChatMessageModel via the real DB.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_chat_sessions_integration.py -v
"""
from __future__ import annotations

import pytest

from db.models import ChatMessageModel, ChatSessionModel


@pytest.mark.integration
class TestChatSessionModelIntegration:
    """ChatSessionModel persistence via the real DB."""

    async def test_insert_and_flush_session(self, db_schema, tenant_id, async_session):
        """A ChatSessionModel can be added, flushed, and refreshed."""
        session = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=999,
            title="Test Session",
        )
        async_session.add(session)
        await async_session.flush()
        await async_session.refresh(session)

        assert session.id is not None
        assert session.tenant_id == tenant_id
        assert session.user_id == 999
        assert session.title == "Test Session"
        assert session.created_at is not None
        assert session.updated_at is not None

    async def test_insert_session_with_null_title(self, db_schema, tenant_id, async_session):
        """title=None is accepted."""
        session = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=999,
            title=None,
        )
        async_session.add(session)
        await async_session.flush()
        await async_session.refresh(session)

        assert session.title is None


@pytest.mark.integration
class TestChatMessageModelIntegration:
    """ChatMessageModel persistence via the real DB."""

    async def test_insert_and_flush_message(self, db_schema, tenant_id, async_session):
        """A ChatMessageModel can be added, flushed, and refreshed."""
        # Create parent session first
        chat_session = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=999,
            title="Session for Messages",
        )
        async_session.add(chat_session)
        await async_session.flush()
        await async_session.refresh(chat_session)

        # Insert message
        msg = ChatMessageModel(
            session_id=chat_session.id,
            tenant_id=tenant_id,
            role="user",
            content="Hello",
            intent="greeting",
        )
        async_session.add(msg)
        await async_session.flush()
        await async_session.refresh(msg)

        assert msg.id is not None
        assert msg.session_id == chat_session.id
        assert msg.tenant_id == tenant_id
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.intent == "greeting"
        assert msg.created_at is not None

    async def test_insert_message_with_null_intent(self, db_schema, tenant_id, async_session):
        """intent=None is accepted."""
        chat_session = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=999,
            title="Session",
        )
        async_session.add(chat_session)
        await async_session.flush()
        await async_session.refresh(chat_session)

        msg = ChatMessageModel(
            session_id=chat_session.id,
            tenant_id=tenant_id,
            role="assistant",
            content="Hello!",
            intent=None,
        )
        async_session.add(msg)
        await async_session.flush()
        await async_session.refresh(msg)

        assert msg.intent is None


@pytest.mark.integration
class TestChatCascadeDeleteIntegration:
    """Cascade delete: removing a session removes its messages."""

    async def test_cascade_delete_removes_messages(
        self, db_schema, tenant_id, async_session
    ):
        """Deleting a ChatSessionModel cascades to child ChatMessageModel rows."""
        # Create session with two messages
        chat_session = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=999,
            title="Cascade Test",
        )
        async_session.add(chat_session)
        await async_session.flush()
        await async_session.refresh(chat_session)

        msg1 = ChatMessageModel(
            session_id=chat_session.id,
            tenant_id=tenant_id,
            role="user",
            content="First",
            intent=None,
        )
        msg2 = ChatMessageModel(
            session_id=chat_session.id,
            tenant_id=tenant_id,
            role="assistant",
            content="Second",
            intent=None,
        )
        async_session.add(msg1)
        async_session.add(msg2)
        await async_session.flush()
        await async_session.refresh(msg1)
        await async_session.refresh(msg2)

        # Verify both messages are present
        assert msg1.id is not None
        assert msg2.id is not None

        # Delete the parent session
        await async_session.delete(chat_session)
        await async_session.flush()

        # Verify messages are gone (re-fetch by ID returns None)
        result = await async_session.get(ChatMessageModel, msg1.id)
        assert result is None
        result = await async_session.get(ChatMessageModel, msg2.id)
        assert result is None
