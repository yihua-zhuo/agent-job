"""Enrichment API router — ``POST /api/v1/enrichment/lookup``."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.enrichment import EnrichmentLookupRequest
from services.enrichment_service import EnrichmentService

enrichment_router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}


@enrichment_router.post("/lookup")
async def lookup(
    request: EnrichmentLookupRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
    customer_id: int = Query(..., description="ID of the customer to associate the enrichment with"),
) -> dict:
    """Look up company enrichment data by domain or company name.

    Calls the configured third-party provider (Clearbit) and persists
    the raw response to ``customer_enrichments``.
    """
    svc = EnrichmentService(session)
    result = await svc.lookup(
        domain=request.domain,
        company_name=request.company_name,
        customer_id=customer_id,
    )
    return _success(result)
