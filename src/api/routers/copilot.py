"""Copilot router — /copilot/chat and /copilot/{conversation_id}/history endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import UnauthorizedException
from services.copilot_service import CopilotService

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/chat")
async def chat(
    message: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Accept a user message, persist it, and return a copilot response with tool_calls."""
    if ctx.user_id is None:
        raise UnauthorizedException("user_id is required for chat")

    svc = CopilotService(session)
    conversation = await svc.get_or_create_conversation(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        channel="copilot",
    )
    await svc.persist_message(
        conversation_id=conversation.id,
        tenant_id=ctx.tenant_id,
        role="user",
        content=message,
    )

    return {
        "success": True,
        "data": {
            "response": f"You said: {message}",
            "tool_calls": [],
        },
    }


@router.get("/{conversation_id}/history")
async def history(
    conversation_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return the most recent 20 messages for a conversation."""
    svc = CopilotService(session)
    messages, total = await svc.get_history(
        conversation_id=conversation_id,
        tenant_id=ctx.tenant_id,
    )
    return {
        "success": True,
        "data": {
            "messages": [m.to_dict() for m in messages],
            "total": total,
        },
    }
