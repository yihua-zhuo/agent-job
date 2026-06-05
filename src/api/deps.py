"""FastAPI dependency-injection wiring.

This module is the single import surface for all DI providers used in
routers. It re-exports the existing session and auth dependencies and adds
``get_llm_service`` and ``get_agent_service`` so routers can wire up agent
dispatching via the standard FastAPI Depends mechanism.
"""

from __future__ import annotations

from fastapi import Depends
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
]


def get_llm_service(session: AsyncSession = Depends(get_db)) -> LLMService:
    """Build a request-scoped LLMService bound to the current request's session."""
    return LLMService(session)


def get_agent_service(
    session: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
) -> AgentService:
    """Build a request-scoped AgentService with the shared registry singleton."""
    return AgentService(session, llm_service, AgentRegistry())
