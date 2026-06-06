"""Events router — POST /engagement webhook for customer engagement events."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models.customer import CustomerModel
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.event_service import EventService
from services.score_service import ScoreService

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class EngagementEventRequest(BaseModel):
    customer_id: int = Field(..., gt=0)
    event_type: str = Field(..., pattern="^(email_open|website_visit)$")
    event_metadata: dict | None = None


@router.post("/engagement", status_code=200)
async def create_engagement_event(
    body: EngagementEventRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Record an engagement event, recalculate the customer's score, and persist the result."""
    event_svc = EventService(session)
    score_svc = ScoreService(session)

    await event_svc.record_engagement_event(
        tenant_id=ctx.tenant_id,
        customer_id=body.customer_id,
        event_type=body.event_type,
        event_metadata=body.event_metadata,
    )
    result = await score_svc.calculate_score(
        customer_id=body.customer_id,
        tenant_id=ctx.tenant_id,
    )
    # ScoreService.calculate_score is read-only — persist the recalculated
    # score/tier back to the customer row so the change survives commit.
    customer_result = await session.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.id == body.customer_id,
                CustomerModel.tenant_id == ctx.tenant_id,
            )
        )
    )
    customer = customer_result.scalar_one_or_none()
    if customer is not None:
        customer.score = result.score
        customer.tier = result.tier_label
        await session.flush()
    return {
        "success": True,
        "data": {
            "customer_id": body.customer_id,
            "score": result.score,
            "tier": result.tier_label,
        },
        "message": "Engagement event recorded successfully",
    }
