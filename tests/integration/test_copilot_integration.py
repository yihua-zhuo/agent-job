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
        from sqlalchemy import select

        from db.models.user import UserModel

        result = await async_session.execute(select(UserModel).where(UserModel.tenant_id == tenant_id_web))
        user = result.scalar_one_or_none()
        assert user is not None, f"No user found for tenant {tenant_id_web} — auth_headers_web must run first"
        user_id = user.id
        conv = await seed_conversation(async_session, tenant_id_web, user_id=user_id)
        await seed_message(async_session, conv.id, tenant_id_web, "user", "Hello!")
        await seed_message(async_session, conv.id, tenant_id_web, "assistant", "Hi there!")

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
        from sqlalchemy import select

        from db.models.user import UserModel

        result = await async_session.execute(select(UserModel).where(UserModel.tenant_id == tenant_id_web))
        user = result.scalar_one_or_none()
        assert user is not None, f"No user found for tenant {tenant_id_web} — auth_headers_web must run first"
        user_id = user.id
        conv = await seed_conversation(async_session, tenant_id_web, user_id=user_id)
        for i in range(25):
            await seed_message(async_session, conv.id, tenant_id_web, "user", f"Message {i}")

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
        # Seed users for both tenants so the copilot service can find them when
        # creating conversations — matching the pattern used for tenant 1 below.
        await seed_user(async_session, tenant_id_web, _TENANT_1_USER_ID)
        await seed_user(async_session, tenant_id_2_web, _TENANT_2_USER_ID)

        # Create a conversation in tenant 1 so there IS something to find.
        conv_tenant_1 = await seed_conversation(async_session, tenant_id_web, _TENANT_1_USER_ID)
        await seed_message(async_session, conv_tenant_1.id, tenant_id_web, "user", "Tenant 1 message")

        # Chat as tenant 2 — should get its own new conversation, not tenant 1's.
        response_tenant_2 = await api_client_tenant_2.post("/copilot/chat?message=hello")
        assert response_tenant_2.status_code == 200
        data_tenant_2 = response_tenant_2.json()
        assert data_tenant_2["success"] is True

        # Retrieve tenant 2's conversation from the DB (chat response doesn't include conversation_id).
        from sqlalchemy import select

        from db.models.conversation import ConversationModel

        result = await async_session.execute(
            select(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id_2_web)
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        conv_tenant_2 = result.scalar_one_or_none()
        assert conv_tenant_2 is not None, "Tenant 2 should have a conversation after calling chat"

        # Verify tenant 2 cannot access tenant 1's conversation (cross-tenant isolation).
        history_cross = await api_client_tenant_2.get(f"/copilot/{conv_tenant_1.id}/history")
        assert history_cross.status_code == 404
        body = history_cross.json()
        assert body["success"] is False, f"Expected success=False for cross-tenant access, got: {body}"

        # Verify tenant 1 cannot access tenant 2's conversation (reverse-direction isolation).
        history_reverse = await api_client.get(f"/copilot/{conv_tenant_2.id}/history")
        assert history_reverse.status_code == 404
        body_reverse = history_reverse.json()
        assert body_reverse["success"] is False, f"Expected success=False for reverse cross-tenant access, got: {body_reverse}"
