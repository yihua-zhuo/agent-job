"""Copilot router — /copilot/chat and /copilot/{conversation_id}/history endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.copilot_service import CopilotService

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/chat")
async def chat(
    message: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Accept a user message, persist it, and return a copilot response with tool_calls."""
    svc = CopilotService(session)
    ai_response = await svc.chat(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        message=message,
    )
    return {
        "success": True,
        "data": {
            "response": ai_response.reply,
            # tool_calls populated once the tool-calling loop is wired;
            # get_tool_registry()['deferred'] gates availability.
            "tool_calls": getattr(ai_response, "tool_calls", []) or [],
        },
    }


@router.get("/{conversation_id}/history")
async def history(
    conversation_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return all messages for a conversation (service enforces its 20-message cap server-side)."""
    svc = CopilotService(session)
    # get_history() already filters by tenant_id; if no conversation exists for this
    # tenant, it returns an empty list with total=0 — a reasonable empty-state response.
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
