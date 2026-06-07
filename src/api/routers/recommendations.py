"""Recommendations router — GET /api/v1/sales/opportunities/{opportunity_id}/recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import ValidationException
from services.recommendation_service import RecommendationService

recommendations_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


@recommendations_router.get("/opportunities/{opportunity_id}/recommendations")
async def get_opportunity_recommendations(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    if ctx.tenant_id is None:
        raise ValidationException("Tenant ID is required")
    service = RecommendationService(session)
    result = await service.get_recommendations(opportunity_id, ctx.tenant_id)
    return {
        "success": True,
        "data": result.to_dict(),
        "message": "Recommendations fetched",
    }
