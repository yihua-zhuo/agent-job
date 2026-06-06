"""Events router — POST /engagement webhook for customer engagement events."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.event_service import EventService
from services.score_service import ScoreService

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class EngagementEventRequest(BaseModel):
    customer_id: int = Field(..., gt=0)
    event_type: str = Field(..., pattern="^(email_open|website_visit)$")
    metadata: dict | None = None


@router.post("/engagement")
async def create_engagement_event(
    body: EngagementEventRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Record an engagement event and trigger a score recalculation for the customer."""
    event_svc = EventService(session)
    score_svc = ScoreService(session)

    await event_svc.record_engagement_event(
        tenant_id=ctx.tenant_id,
        customer_id=body.customer_id,
        event_type=body.event_type,
        metadata=body.metadata,
    )
    result = await score_svc.calculate_score(
        customer_id=body.customer_id,
        tenant_id=ctx.tenant_id,
    )
    return {
        "success": True,
        "data": {
            "customer_id": body.customer_id,
            "score": result.score,
            "tier": result.tier_label,
        },
    }
