"""Enrichment API router — ``POST /api/v1/enrichment/lookup`` and ``POST /api/v1/enrichment/refresh/{customer_id}``."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.enrichment import EnrichmentLookupRequest, EnrichmentRefreshRequest
from services.enrichment_service import EnrichmentService

enrichment_router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}


@enrichment_router.post("/lookup")
async def lookup(
    request: EnrichmentLookupRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Look up company enrichment data by domain or company name.

    Calls the configured third-party provider (Clearbit) and persists
    the raw response to ``customer_enrichments``.
    """
    svc = EnrichmentService(session)
    result, _raw_data = await svc.lookup(
        domain=request.domain,
        company_name=request.company_name,
        tenant_id=ctx.tenant_id,
        customer_id=request.customer_id,
    )
    return _success(result)


@enrichment_router.post("/refresh/{customer_id}")
async def refresh_enrichment(
    customer_id: int = Path(..., ge=1, le=2147483647, description="Customer ID to refresh"),
    body: EnrichmentRefreshRequest | None = None,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Re-call the enrichment provider for an existing customer and upsert the record.

    Uses the domain or company_name from the optional request body if provided;
    otherwise falls back to the enrichment data already on record.
    """
    svc = EnrichmentService(session)
    result, upserted = await svc.refresh_full(
        customer_id=customer_id,
        tenant_id=ctx.tenant_id,
        domain_override=body.domain if body else None,
        company_name_override=body.company_name if body else None,
    )
    data = dict(result)
    if upserted is not None:
        data["last_enriched_at"] = upserted.enriched_at.isoformat() if upserted.enriched_at else None
        if upserted.next_refresh_at is not None and upserted.next_refresh_at <= datetime.now(UTC):
            data["enrichment_status"] = "stale"
        else:
            data["enrichment_status"] = "enriched"
    else:
        data["last_enriched_at"] = None
        data["enrichment_status"] = "none"
    return _success(data)
