"""AI Chat Assistant router — /api/v1/ai endpoints."""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.ai import (
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)
from pkg.errors.app_exceptions import ValidationException
from services.ai_service import AIService

ai_router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# Rate limiting — in-memory sliding window, keyed by tenant_id
# ---------------------------------------------------------------------------

_rate_limit_store: defaultdict[int, list[float]] = defaultdict(list)

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 30  # requests


def _check_rate_limit(tenant_id: int) -> None:
    """Raise ValidationException if tenant exceeds the rate limit."""
    now = time.time()
    window = _rate_limit_store[tenant_id]
    # Retain only timestamps within the sliding window
    window[:] = [ts for ts in window if now - ts < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        raise ValidationException("Rate limit exceeded")
    window.append(now)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@ai_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Send a message to the AI assistant.

    If ``conversation_id`` is absent, a new conversation is created first.
    CRM context is automatically enriched before calling the AI gateway.
    """
    _check_rate_limit(ctx.tenant_id)

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

    return {
        "success": True,
        "data": ChatResponse(
            reply=result.reply,
            suggestions=result.suggestions,
            actions=result.actions,
        ).model_dump(),
    }


@ai_router.post("/conversation", status_code=201)
async def create_conversation(
    request: CreateConversationRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new AI conversation."""
    _check_rate_limit(ctx.tenant_id)

    svc = AIService(session)
    conversation = await svc.create_conversation(
        tenant_id=ctx.tenant_id, user_id=ctx.user_id, title=request.title
    )

    return {
        "success": True,
        "data": ConversationResponse(
            id=conversation.id,
            title=conversation.title or "",
            created_at=conversation.created_at.isoformat() if conversation.created_at else "",
            updated_at=conversation.updated_at.isoformat() if conversation.updated_at else "",
        ).model_dump(),
    }


@ai_router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return conversation metadata and its message list."""
    _check_rate_limit(ctx.tenant_id)

    svc = AIService(session)

    # Verify the conversation exists and belongs to this tenant
    conversation = await svc.get_conversation(conversation_id, ctx.tenant_id)

    messages = await svc.get_conversation_messages(conversation_id, ctx.tenant_id, limit=100)

    return {
        "success": True,
        "data": ConversationDetailResponse(
            id=conversation.id,
            title=conversation.title or "",
            created_at=conversation.created_at.isoformat() if conversation.created_at else "",
            updated_at=conversation.updated_at.isoformat() if conversation.updated_at else "",
            messages=[
                MessageResponse(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at.isoformat() if m.created_at else "",
                )
                for m in messages
            ],
        ).model_dump(),
    }
