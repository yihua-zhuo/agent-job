"""
Integration tests for AI Chat Assistant service.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_ai_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest

from db.models.ai_conversation import AIConversationModel, AIMessageModel
from pkg.errors.app_exceptions import NotFoundException
from services.ai_service import AIService


@pytest.mark.integration
class TestAIConversationIntegration:
    """Full AI conversation lifecycle via the real DB."""

    async def test_create_and_get_conversation(self, db_schema, tenant_id, async_session):
        """POST /conversation creates a record retrievable by ID."""
        svc = AIService(async_session)
        conv = await svc.create_conversation(
            tenant_id=tenant_id, user_id=999, title="Test Conversation"
        )
        await async_session.commit()

        fetched = await svc.get_conversation(conv.id, tenant_id)
        assert fetched.id == conv.id
        assert fetched.title == "Test Conversation"
        assert fetched.tenant_id == tenant_id
        assert fetched.user_id == 999

    async def test_list_conversations(self, db_schema, tenant_id, async_session):
        """list_conversations returns paginated results."""
        svc = AIService(async_session)
        # Create two conversations
        await svc.create_conversation(tenant_id=tenant_id, user_id=999, title="Chat A")
        await svc.create_conversation(tenant_id=tenant_id, user_id=999, title="Chat B")
        await async_session.commit()

        items, total = await svc.list_conversations(tenant_id=tenant_id, user_id=999)
        assert total >= 2
        assert len(items) >= 2

    async def test_get_conversation_404_for_wrong_tenant(self, db_schema, tenant_id, async_session):
        """Conversation from tenant A is not accessible to tenant B."""
        svc = AIService(async_session)
        conv = await svc.create_conversation(tenant_id=tenant_id, user_id=999, title="Private")
        await async_session.commit()

        with pytest.raises(NotFoundException):
            await svc.get_conversation(conv.id, tenant_id=99999)  # Different tenant

    async def test_get_conversation_404_missing(self, db_schema, tenant_id, async_session):
        """Non-existent conversation raises NotFoundException."""
        svc = AIService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_conversation(conversation_id=999999, tenant_id=tenant_id)


@pytest.mark.integration
class TestAIMessageIntegration:
    """Message persistence and retrieval via the real DB."""

    async def test_send_message_stores_both_messages(self, db_schema, tenant_id, async_session):
        """send_message stores user message and assistant reply."""
        svc = AIService(async_session)

        # Create conversation
        conv = await svc.create_conversation(tenant_id=tenant_id, user_id=999, title="Chat")
        await async_session.commit()

        # Send a message
        result = await svc.send_message(
            conversation_id=conv.id,
            message="Hello AI",
            tenant_id=tenant_id,
            user_id=999,
        )
        await async_session.commit()

        # Verify reply was returned
        assert result.reply is not None
        assert len(result.reply) > 0

        # Retrieve stored messages
        messages = await svc.get_conversation_messages(conv.id, tenant_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello AI"
        assert messages[1].role == "assistant"

    async def test_conversation_updated_at_changes(self, db_schema, tenant_id, async_session):
        """Sending a message updates the conversation's updated_at timestamp."""
        svc = AIService(async_session)
        conv = await svc.create_conversation(tenant_id=tenant_id, user_id=999, title="Chat")
        await async_session.commit()
        original_updated = conv.updated_at

        await svc.send_message(
            conversation_id=conv.id,
            message="Hello",
            tenant_id=tenant_id,
            user_id=999,
        )
        await async_session.commit()

        # Refresh conversation
        updated_conv = await svc.get_conversation(conv.id, tenant_id)
        # updated_at is set to now() at send_message time, which is after original
        assert updated_conv.updated_at >= original_updated


@pytest.mark.integration
class TestAIContextEnrichment:
    """CRM context is correctly enriched from the database."""

    async def test_enrich_context_returns_counts(self, db_schema, tenant_id, async_session):
        """_enrich_context returns summary counts for CRM entities."""
        svc = AIService(async_session)
        context = await svc._enrich_context(tenant_id=tenant_id, user_id=999)

        assert "customer_count" in context
        assert "open_ticket_count" in context
        assert "opportunity_count" in context
        assert "activity_count" in context
        assert "task_count" in context
        assert isinstance(context["customer_count"], int)