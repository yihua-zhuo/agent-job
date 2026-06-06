"""Recommendations router — GET /api/v1/sales/opportunities/{opportunity_id}/recommendations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.sales_recommendation import SalesRecommendationService

recommendations_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


@recommendations_router.get("/opportunities/{opportunity_id}/recommendations")
async def get_opportunity_recommendations(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    if ctx.tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    service = SalesRecommendationService()
    result = await service.get_recommendations(opportunity_id, ctx.tenant_id)
    next_action = result.next_best_action
    return {
        "success": True,
        "data": {
            "opportunity_id": result.opportunity_id,
            "conversion_probability": result.conversion_probability,
            "similar_opportunities": result.similar_opportunities,
            "next_best_action": {
                "action": next_action.action,
                "target": next_action.target,
                "reason": next_action.reason,
                "confidence": next_action.confidence,
            }
            if next_action is not None
            else None,
        },
        "message": "Recommendations fetched",
    }
