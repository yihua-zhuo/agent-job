"""Integration tests for the copilot router against real PostgreSQL."""

from __future__ import annotations

import pytest

from tests.integration.domain_fixtures.copilot import seed_conversation, seed_message, seed_user

pytestmark = pytest.mark.integration


# Stable user IDs used for copilot integration tests.
# _TENANT_1_USER_ID = 999 — matches JWT user_id hard-coded in auth_headers_web fixture.
# _TENANT_2_USER_ID = 998 — matches JWT user_id hard-coded in auth_headers_tenant_2 fixture.
_TENANT_1_USER_ID = 999
_TENANT_2_USER_ID = 998


class TestCopilotIntegration:
    """End-to-end integration tests for copilot router endpoints."""

    async def test_chat_integration(self, db_schema, api_client, async_session, tenant_id_web: int):
        """POST /copilot/chat returns 200 with {"success": True, ...}."""
        from sqlalchemy import select

        from db.models.user import UserModel

        # Get the actual user ID for tenant 1 from the auth token by querying the DB.
        result = await async_session.execute(select(UserModel).where(UserModel.tenant_id == tenant_id_web))
        user = result.scalar_one_or_none()
        if user is None:
            user_id = _TENANT_1_USER_ID
            await seed_user(async_session, tenant_id_web, user_id)
        else:
            user_id = user.id
            # Expire so subsequent ops hit fresh state.
            async_session.expire_all()

        response = await api_client.post("/copilot/chat?message=hello")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "response" in data["data"]
        assert "tool_calls" in data["data"]

    async def test_history_integration(self, db_schema, async_session, api_client, tenant_id_web: int):
        """GET /copilot/{conv_id}/history returns {"success": True, "messages": [...], "total": N}}."""
        # Use tenant_id_web so seeded data matches the JWT-authenticated tenant.
        conv = await seed_conversation(async_session, tenant_id_web, user_id=1)
        await seed_message(async_session, conv.id, tenant_id_web, "user", "Hello!")
        await seed_message(async_session, conv.id, tenant_id_web, "assistant", "Hi there!")
        # Commit so the API's separate session can see the seeded data.
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
        # Verify newest-first ordering (service sorts by created_at desc).
        assert data["data"]["messages"][0]["role"] == "assistant"
        assert data["data"]["messages"][1]["role"] == "user"

    async def test_history_caps_at_20(self, db_schema, async_session, api_client, tenant_id_web: int):
        """History endpoint returns at most 20 messages even when more are seeded."""
        conv = await seed_conversation(async_session, tenant_id_web, user_id=1)
        for i in range(25):
            await seed_message(async_session, conv.id, tenant_id_web, "user", f"Message {i}")
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
        # Seed distinct user IDs per tenant to avoid primary-key collision.
        await seed_user(async_session, tenant_id_web, _TENANT_1_USER_ID)
        # tenant_id_2_web matches JWT user_id=_TENANT_1_USER_ID (999) in auth_headers_tenant_2.
        await seed_user(async_session, tenant_id_2_web, _TENANT_1_USER_ID)
        await async_session.commit()

        # Create a conversation in tenant 1 so there IS something to find.
        conv_tenant_1 = await seed_conversation(async_session, tenant_id_web, _TENANT_1_USER_ID)
        await seed_message(async_session, conv_tenant_1.id, tenant_id_web, "user", "Tenant 1 message")

        # Chat as tenant 2 — should get its own new conversation, not tenant 1's.
        response_tenant_2 = await api_client_tenant_2.post("/copilot/chat?message=hello")
        assert response_tenant_2.status_code == 200
        data_tenant_2 = response_tenant_2.json()
        assert data_tenant_2["success"] is True

        # Verify tenant 2 cannot access tenant 1's conversation.
        history_tenant_2 = await api_client_tenant_2.get(f"/copilot/{conv_tenant_1.id}/history")
        assert history_tenant_2.status_code == 404

        # Verify tenant 2 created its own separate conversation.
        from sqlalchemy import and_, func, select

        from db.models.conversation import ConversationModel
        from db.models.conversation_message import ConversationMessageModel

        # Query conversation ID using tenant_id and user_id (bypasses stale ORM object).
        result = await async_session.execute(
            select(ConversationModel.id).where(
                and_(
                    ConversationModel.tenant_id == tenant_id_2_web,
                    ConversationModel.user_id == _TENANT_1_USER_ID,
                )
            )
        )
        conv_tenant_2_id = result.scalar_one_or_none()
        assert conv_tenant_2_id is not None, "Tenant 2 should have a conversation"

        result2 = await async_session.execute(
            select(func.count(ConversationMessageModel.id)).where(
                and_(
                    ConversationMessageModel.conversation_id == conv_tenant_2_id,
                    ConversationMessageModel.tenant_id == tenant_id_2_web,
                )
            )
        )
        msg_count = result2.scalar()
        assert msg_count == 2
