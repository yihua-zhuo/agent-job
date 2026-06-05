"""FastAPI dependency-injection wiring.

This module is the single import surface for all DI providers used in
routers. It re-exports the existing session and auth dependencies and adds
``get_llm_service`` and ``get_agent_service`` so routers can wire up agent
dispatching via the standard FastAPI Depends mechanism.

The shared ``httpx.AsyncClient`` used by ``LLMService`` is owned by the
application lifecycle (stored in ``app.state.llm_http_client``) and closed
during FastAPI shutdown — see ``main.lifespan``.

``AIChatGateway`` is a stateless stub (no per-request state, no connection
pool), so a module-level singleton is safe. See ``internal.ai_gateway``.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Depends, Request
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
    "shutdown_app_state",
]

logger = logging.getLogger(__name__)

# Module-level singleton — AIChatGateway is stateless and cheap to share.
_ai_gateway = AIChatGateway()


def get_llm_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> LLMService:
    """Build a request-scoped LLMService bound to the current request's session.

    The underlying httpx.AsyncClient is shared across requests and owned by
    ``app.state.llm_http_client``; only the session is request-scoped. If the
    lifespan handler failed to initialise the client, this fails fast at
    request time with a clear message rather than a confusing AttributeError.
    """
    client: httpx.AsyncClient | None = getattr(request.app.state, "llm_http_client", None)
    if client is None:
        raise RuntimeError("llm_http_client is not initialised — main.lifespan must create it at startup")
    return LLMService(session, client=client, owns_client=False)


def get_agent_service(
    session: AsyncSession = Depends(get_db),
) -> AgentService:
    """Build a request-scoped AgentService with the shared registry singleton.

    ``AgentRegistry`` is a process-wide singleton (see ``agents.registry``);
    calling the constructor returns the same instance, so it is safe to do
    inside the dependency.
    """
    return AgentService(session, _ai_gateway, AgentRegistry())


async def shutdown_app_state(app) -> None:
    """Close shared resources stored on ``app.state`` during FastAPI shutdown.

    Wired into the FastAPI lifespan shutdown phase via ``main.create_app()`` —
    the shutdown phase in ``main.lifespan`` calls this function so the
    httpx client is closed deterministically. If the close itself raises,
    we log at warning level so operators see the failure but do not crash
    the shutdown sequence.
    """
    client = getattr(app.state, "llm_http_client", None)
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            logger.warning("llm_http_client.aclose failed during shutdown", exc_info=True)
