"""Seed helpers for copilot integration tests."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert

from db.models.conversation import ConversationModel
from db.models.conversation_message import ConversationMessageModel
from db.models.user import UserModel


async def seed_conversation(async_session, tenant_id: int, user_id: int):
    """Seed a conversation record and return the ORM object."""
    conv = ConversationModel(
        tenant_id=tenant_id,
        user_id=user_id,
        channel="copilot",
    )
    async_session.add(conv)
    await async_session.flush()
    return conv


async def seed_message(
    async_session,
    conversation_id: int,
    tenant_id: int,
    role: str,
    content: str,
):
    """Seed a single conversation message and return the ORM object."""
    msg = ConversationMessageModel(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
    )
    async_session.add(msg)
    await async_session.flush()
    return msg


async def seed_user(async_session, tenant_id: int, user_id: int):
    """Seed a user record so chat endpoint does not violate FK constraints.

    Uses INSERT ... ON CONFLICT DO NOTHING so that users created by earlier
    fixtures (e.g. auth_headers_tenant_2, which runs in the same test function
    before seed_user) do not cause a unique-violation error on flush().
    """
    stmt = (
        insert(UserModel)
        .values(
            id=user_id,
            tenant_id=tenant_id,
            username=f"testuser_{user_id}",
            email=f"testuser_{user_id}@example.com",
            password_hash="dummy_hash",
            role="admin",
            status="active",
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await async_session.execute(stmt)
    await async_session.flush()
