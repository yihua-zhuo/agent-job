"""FastAPI dependency-injection wiring.

This module is the single import surface for all DI providers used in
routers. It re-exports the existing session and auth dependencies and adds
``get_llm_service`` and ``get_agent_service`` so routers can wire up agent
dispatching via the standard FastAPI Depends mechanism.

The shared ``httpx.AsyncClient`` used by ``LLMService`` is owned by the
application lifecycle (stored in ``app.state.llm_http_client``) and closed
during FastAPI shutdown — see ``main.lifespan``.
"""

from __future__ import annotations

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import AgentRegistry
from db.connection import get_db
from dependencies.auth import get_current_user
from services.agent_service import AgentService
from services.llm_service import LLMService

__all__ = [
    "get_db",
    "get_current_user",
    "get_llm_service",
    "get_agent_service",
    "shutdown_app_state",
]


def get_llm_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> LLMService:
    """Build a request-scoped LLMService bound to the current request's session.

    The underlying httpx.AsyncClient is shared across requests and owned by
    ``app.state.llm_http_client``; only the session is request-scoped.
    """
    client: httpx.AsyncClient = request.app.state.llm_http_client
    return LLMService(session, client=client, owns_client=False)


def get_agent_service(
    session: AsyncSession = Depends(get_db),
) -> AgentService:
    """Build a request-scoped AgentService with the shared registry singleton.

    ``AgentRegistry`` is a process-wide singleton (see ``agents.registry``);
    calling the constructor returns the same instance, so it is safe to do
    inside the dependency.
    """
    from internal.ai_gateway import AIChatGateway

    return AgentService(session, AIChatGateway(), AgentRegistry())


async def shutdown_app_state(app) -> None:
    """Close shared resources stored on ``app.state`` during FastAPI shutdown."""
    client = getattr(app.state, "llm_http_client", None)
    if client is not None:
        await client.aclose()
