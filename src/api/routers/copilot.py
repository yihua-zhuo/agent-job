"""Copilot router — /copilot/chat and /copilot/{conversation_id}/history endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/chat")
async def chat(
    message: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Accept a user message, persist it, and return a copilot response with tool_calls."""
    from sqlalchemy import select

    from db.models.conversation import ConversationModel
    from db.models.conversation_message import ConversationMessageModel

    # Ensure a default conversation exists for this tenant/user.

    result = await session.execute(
        select(ConversationModel).where(
            ConversationModel.tenant_id == ctx.tenant_id,
        ).order_by(ConversationModel.id.desc()).limit(1)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        conversation = ConversationModel(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            channel="copilot",
        )
        session.add(conversation)
        await session.flush()

    # Persist the user message.
    session.add(
        ConversationMessageModel(
            conversation_id=conversation.id,
            tenant_id=ctx.tenant_id,
            role="user",
            content=message,
        )
    )
    await session.flush()

    return {
        "success": True,
        "data": {
            "response": f"You said: {message}",
            "tool_calls": [],
        },
    }


@router.get("/{conversation_id}/history")
async def history(
    conversation_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return the most recent 20 messages for a conversation."""
    from sqlalchemy import and_, select

    from db.models.conversation_message import ConversationMessageModel

    result = await session.execute(
        select(ConversationMessageModel).where(
            and_(
                ConversationMessageModel.conversation_id == conversation_id,
                ConversationMessageModel.tenant_id == ctx.tenant_id,
            )
        ).order_by(ConversationMessageModel.created_at.desc())
    )
    messages = list(result.scalars().all())[:20]
    return {
        "success": True,
        "data": {
            "messages": [m.to_dict() for m in messages],
            "total": len(messages),
        },
    }
