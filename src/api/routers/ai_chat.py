"""AI Chat router — /api/v1/ai/chat and /api/v1/ai/sessions endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.ai import ChatRequest, ChatResponse
from services.ai_service import AIService

ai_chat_router = APIRouter(prefix="/api/v1/ai", tags=["ai-chat"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@ai_chat_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AIService(session)
    if request.conversation_id is None:
        conversation = await svc.create_conversation(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id, title=None
        )
        conversation_id = conversation.id
    else:
        conversation_id = request.conversation_id
    result = await svc.send_message(
        conversation_id=conversation_id,
        message=request.message,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
    )
    response = ChatResponse(
        reply=result.reply,
        suggestions=result.suggestions,
        actions=result.actions,
    )
    return _success(response.to_dict(), message=result.reply or "")


@ai_chat_router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AIService(session)
    conversations, total = await svc.list_conversations(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        page=page,
        page_size=page_size,
    )
    return _paginated_response(
        items=[c.to_dict() for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )
