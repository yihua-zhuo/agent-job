"""Health router — exposes LLM and agent-registry status for monitoring.

``GET /health/live`` is a public liveness probe (no auth) suitable for k8s
liveness/load-balancer checks. ``GET /health/agents`` is a detailed
authenticated view of the agent registry and LLM status, behind ``require_auth``
so it can only be called by authenticated callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from api.deps import get_agent_service
from internal.middleware.fastapi_auth import AuthContext, require_auth

if TYPE_CHECKING:
    from services.agent_service import AgentService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def health_live() -> dict:
    """Public liveness probe — no auth, no DB access. Returns 200 if the process is up."""
    return {"status": "ok"}


@router.get("/agents")
async def get_agents_health(
    agent_svc: AgentService = Depends(get_agent_service),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    status = await agent_svc.get_status(tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": status.to_dict(),
        "message": "Agent health retrieved successfully",
    }
