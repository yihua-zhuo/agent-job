"""Health router — exposes LLM and agent-registry status for monitoring."""

from fastapi import APIRouter, Depends

from api.deps import get_agent_service
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.agent_service import AgentService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/agents")
async def get_agents_health(
    agent_svc: AgentService = Depends(get_agent_service),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    status = await agent_svc.get_status(tenant_id=ctx.tenant_id)
    return {"success": True, "data": status}
