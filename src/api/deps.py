"""FastAPI dependency-injection wiring.

This module is the single import surface for all DI providers used in
routers. It re-exports the existing session and auth dependencies and adds
``get_llm_service`` and ``get_agent_service`` so routers can wire up agent
dispatching via the standard FastAPI Depends mechanism.
"""

from __future__ import annotations

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import AgentRegistry
from db.connection import get_db
from dependencies.auth import get_current_user
from internal.ai_gateway import AIChatGateway
from services.agent_service import AgentService
from services.llm_service import LLMService

__all__ = [
    "get_db",
    "get_current_user",
    "get_llm_service",
    "get_agent_service",
]


# Module-level shared httpx.AsyncClient — instantiated lazily and shared
# across all LLMService instances to avoid leaking connections on every
# request.
_llm_http_client: httpx.AsyncClient | None = None


def _get_shared_http_client() -> httpx.AsyncClient:
    """Return the module-level shared httpx.AsyncClient, creating it on first use."""
    global _llm_http_client
    if _llm_http_client is None:
        _llm_http_client = httpx.AsyncClient(timeout=30.0)
    return _llm_http_client


async def get_llm_service(session: AsyncSession = Depends(get_db)) -> LLMService:
    """Build a request-scoped LLMService bound to the current request's session.

    The underlying httpx.AsyncClient is shared across requests (see
    ``_get_shared_http_client``) — only the session is request-scoped.
    """
    return LLMService(session, client=_get_shared_http_client())


def get_agent_service(
    session: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),  # noqa: ARG001 — reserved for future LLM-backed agents
) -> AgentService:
    """Build a request-scoped AgentService with the shared registry singleton.

    ``AgentRegistry`` is a process-wide singleton (see ``agents.registry``);
    calling the constructor returns the same instance, so it is safe to do
    inside the dependency.
    """
    return AgentService(session, AIChatGateway(), AgentRegistry())
