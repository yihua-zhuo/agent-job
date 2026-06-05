"""Health router — exposes LLM and agent-registry status for monitoring."""

from fastapi import APIRouter, Depends

from api.deps import get_agent_service
from services.agent_service import AgentService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/agents")
async def get_agents_health(
    agent_svc: AgentService = Depends(get_agent_service),
) -> dict:
    """Return LLM and agent-registry status."""
    status = await agent_svc.get_status()
    return {"success": True, "data": status}
