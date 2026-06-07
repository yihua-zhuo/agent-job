"""
Integration tests for AI Chat router — /api/v1/ai/chat and /api/v1/ai/sessions.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_ai_chat_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""

import base64
import json

import pytest


def _decode_jwt_payload(auth_headers: dict[str, str]) -> dict:
    """Decode the JWT payload from auth headers to get tenant_id and user_id."""
    token = auth_headers["Authorization"].split(" ")[1]
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


@pytest.mark.integration
class TestAIChatRouterIntegration:
    """End-to-end router → service → DB round-trip for AI chat endpoints."""

    async def test_post_chat_creates_conversation_and_returns_reply(
        self, db_schema, async_session, api_client: "AsyncClient"
    ):
        """POST /api/v1/ai/chat with no conversation_id auto-creates one and returns a reply."""
        await async_session.flush()
        resp = await api_client.post("/api/v1/ai/chat", json={"message": "你好"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "reply" in body["data"]
        assert len(body["data"]["reply"]) > 0

    async def test_post_chat_with_conversation_id_continues_conversation(
        self, db_schema, async_session, api_client: "AsyncClient"
    ):
        """POST /api/v1/ai/chat with a conversation_id appends to that conversation."""
        await async_session.flush()

        payload = _decode_jwt_payload(api_client.headers)
        tenant_id = payload["tenant_id"]
        user_id = payload["user_id"]

        from services.ai_service import AIService

        svc = AIService(async_session)
        conv = await svc.create_conversation(tenant_id=tenant_id, user_id=user_id, title="Test Chat")
        await async_session.commit()
        conversation_id = conv.id

        resp = await api_client.post(
            "/api/v1/ai/chat",
            json={"message": "继续对话", "conversation_id": conversation_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "reply" in body["data"]

    async def test_get_sessions_returns_paginated_list(
        self, db_schema, async_session, api_client: "AsyncClient"
    ):
        """GET /api/v1/ai/sessions returns a paginated list of conversations."""
        await async_session.flush()

        payload = _decode_jwt_payload(api_client.headers)
        tenant_id = payload["tenant_id"]
        user_id = payload["user_id"]

        from services.ai_service import AIService

        svc = AIService(async_session)
        await svc.create_conversation(tenant_id=tenant_id, user_id=user_id, title="Session A")
        await async_session.commit()

        resp = await api_client.get("/api/v1/ai/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "total" in body["data"]
        assert "page" in body["data"]
        assert "page_size" in body["data"]
        assert "total_pages" in body["data"]
        assert body["data"]["total"] >= 1
        assert len(body["data"]["items"]) >= 1

    async def test_get_sessions_pagination(
        self, db_schema, async_session, api_client: "AsyncClient"
    ):
        """GET /api/v1/ai/sessions with pagination params returns correct shape."""
        await async_session.flush()
        resp = await api_client.get("/api/v1/ai/sessions?page=1&page_size=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 5

    async def test_sessions_are_tenant_isolated(
        self,
        db_schema,
        async_session,
        api_client: "AsyncClient",
        api_client_tenant_2: "AsyncClient",
    ):
        """Sessions created by tenant A are not visible to tenant B."""
        await async_session.flush()

        payload = _decode_jwt_payload(api_client.headers)
        tenant_id = payload["tenant_id"]
        user_id = payload["user_id"]

        from services.ai_service import AIService

        svc = AIService(async_session)
        await svc.create_conversation(tenant_id=tenant_id, user_id=user_id, title="Tenant A Session")
        await async_session.commit()

        # Tenant B's sessions should not include tenant A's session
        resp2 = await api_client_tenant_2.get("/api/v1/ai/sessions")
        assert resp2.status_code == 200
        body2 = resp2.json()
        # No sessions for tenant 2 (never created any)
        assert body2["data"]["total"] == 0
        assert body2["data"]["items"] == []