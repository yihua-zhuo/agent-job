"""Pydantic request / response schemas for the AI Chat Assistant API."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for ``POST /api/v1/ai/chat``."""

    message: str = Field(..., min_length=1, max_length=4000)
    context: dict[str, Any] | None = Field(default=None)
    conversation_id: int | None = Field(default=None)


class ChatResponse(BaseModel):
    """Response body for ``POST /api/v1/ai/chat``."""

    reply: str
    suggestions: list[str] | None = None
    actions: list[dict] | None = None


class CreateConversationRequest(BaseModel):
    """Request body for ``POST /api/v1/ai/conversation``."""

    title: str | None = Field(default=None, max_length=200)


class ConversationResponse(BaseModel):
    """Response body for ``POST /api/v1/ai/conversation``."""

    id: int
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Single message in a conversation."""

    id: int
    role: str
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    """Response body for ``GET /api/v1/ai/conversation/{id}``."""

    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageResponse]
