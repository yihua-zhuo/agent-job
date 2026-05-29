"""Integration tests for the copilot router against real PostgreSQL."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _seed_conversation(async_session, tenant_id: int, user_id: int):
    """Seed a conversation record and return the ORM object."""
    from db.models.conversation import ConversationModel

    conv = ConversationModel(
        tenant_id=tenant_id,
        user_id=user_id,
        channel="copilot",
    )
    async_session.add(conv)
    await async_session.flush()
    return conv


async def _seed_message(
    async_session,
    conversation_id: int,
    tenant_id: int,
    role: str,
    content: str,
):
    """Seed a single conversation message and return the ORM object."""
    from db.models.conversation_message import ConversationMessageModel

    msg = ConversationMessageModel(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
    )
    async_session.add(msg)
    await async_session.flush()
    return msg


async def _seed_user(async_session, tenant_id: int, user_id: int):
    """Seed a user record so chat endpoint does not violate FK constraints."""
    from sqlalchemy import select

    from db.models.user import UserModel

    # Check if user already exists (id is globally unique across tenants).
    result = await async_session.execute(select(UserModel).where(UserModel.id == user_id))
    if result.scalar_one_or_none() is not None:
        return  # already seeded
    user = UserModel(
        id=user_id,
        tenant_id=tenant_id,
        username=f"testuser_{user_id}",
        email=f"testuser_{user_id}@example.com",
        password_hash="dummy_hash",
        role="admin",
        status="active",
    )
    async_session.add(user)
    await async_session.flush()
    return user


class TestCopilotIntegration:
    """End-to-end integration tests for copilot router endpoints."""

    async def test_chat_integration(self, api_client, async_session, tenant_id_web: int):
        """POST /copilot/chat returns 200 with {"success": True, ...}."""
        # Seed user 999 (hardcoded in mock auth override) in the same tenant.
        await _seed_user(async_session, tenant_id_web, user_id=999)

        response = await api_client.post("/copilot/chat?message=hello")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "response" in data["data"]
        assert "tool_calls" in data["data"]

    async def test_history_integration(
        self, db_schema, async_session, api_client, tenant_id_web: int
    ):
        """GET /copilot/{conv_id}/history returns {"success": True, "messages": [...], "total": N}}."""
        # Use tenant_id_web so seeded data matches the JWT-authenticated tenant.
        conv = await _seed_conversation(async_session, tenant_id_web, user_id=1)
        await _seed_message(async_session, conv.id, tenant_id_web, "user", "Hello!")
        await _seed_message(async_session, conv.id, tenant_id_web, "assistant", "Hi there!")
        await async_session.commit()

        response = await api_client.get(f"/copilot/{conv.id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "messages" in data["data"]
        assert "total" in data["data"]
        assert isinstance(data["data"]["messages"], list)
        assert data["data"]["total"] == 2
        assert len(data["data"]["messages"]) == 2

    async def test_history_caps_at_20(
        self, db_schema, async_session, api_client, tenant_id_web: int
    ):
        """History endpoint returns at most 20 messages even when more are seeded."""
        conv = await _seed_conversation(async_session, tenant_id_web, user_id=1)
        for i in range(25):
            await _seed_message(async_session, conv.id, tenant_id_web, "user", f"Message {i}")
        await async_session.commit()

        response = await api_client.get(f"/copilot/{conv.id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["messages"]) == 20
        assert data["data"]["total"] == 25

    async def test_chat_cross_tenant_isolation(
        self,
        db_schema,
        async_session,
        api_client,
        api_client_tenant_2,
        tenant_id_web: int,
        tenant_id_2_web: int,
    ):
        """A second tenant gets its own conversation, not the first tenant's."""
        # Seed user 999 in both tenants.
        await _seed_user(async_session, tenant_id_web, user_id=999)
        await _seed_user(async_session, tenant_id_2_web, user_id=999)
        await async_session.commit()

        # Create a conversation in tenant 1 (with user 999) so there IS something to find.
        conv_tenant_1 = await _seed_conversation(
            async_session, tenant_id_web, user_id=999
        )
        await _seed_message(
            async_session, conv_tenant_1.id, tenant_id_web, "user", "Tenant 1 message"
        )
        await async_session.commit()

        # Chat as tenant 2 with the same user_id — should get its own new conversation.
        response_tenant_2 = await api_client_tenant_2.post("/copilot/chat?message=hello")
        assert response_tenant_2.status_code == 200
        data_tenant_2 = response_tenant_2.json()
        assert data_tenant_2["success"] is True

        # Verify tenant 2's history only shows tenant 2 messages, not tenant 1's.
        history_tenant_2 = await api_client_tenant_2.get(f"/copilot/{conv_tenant_1.id}/history")
        # Tenant 2 should have no messages for tenant 1's conversation_id.
        assert history_tenant_2.status_code == 200
        history_data = history_tenant_2.json()
        # Tenant 2 has no messages in the DB for conv_tenant_1, but since the
        # conversation belongs to tenant 1 the query filters it out via tenant_id.
        # The endpoint should return an empty list (no cross-tenant data leak).
        assert history_data["data"]["messages"] == []
