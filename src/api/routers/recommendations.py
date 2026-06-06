"""Recommendations router — GET /api/v1/sales/opportunities/{id}/recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.sales_recommendation import SalesRecommendationService

recommendations_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


@recommendations_router.get("/opportunities/{opp_id}/recommendations")
async def get_opportunity_recommendations(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesRecommendationService(session)
    data = await service.get_recommendations(opp_id, ctx.tenant_id)
    return {"success": True, "data": data}
