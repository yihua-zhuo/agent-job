"""SLA router — /api/v1/sla/summary endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth, AuthContext
from services.sla_service import SLAService
from models.response import ResponseStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope


sla_router = APIRouter(prefix='/api/v1/sla', tags=['sla'])


def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


class SLASummaryData(BaseModel):
    breached: int = Field(..., ge=0)
    at_risk: int = Field(..., ge=0)
    on_track: int = Field(..., ge=0)
    total_tickets: int = Field(..., ge=0)


class SLASummaryResponse(SuccessEnvelope):
    data: SLASummaryData


@sla_router.get(
    '/summary',
    response_model=SLASummaryResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_sla_summary(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Return aggregated SLA counts for the current tenant's tickets."""
    if ctx.tenant_id is None or ctx.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    service = SLAService(session)
    resp = await service.get_summary(tenant_id=ctx.tenant_id)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    return SLASummaryResponse(message=resp.message, data=SLASummaryData(**resp.data))
