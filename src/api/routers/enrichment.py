"""Enrichment API router — ``POST /api/v1/enrichment/lookup``."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models.customer_enrichment import CustomerEnrichmentModel
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
    result = await svc.lookup(
        domain=request.domain,
        company_name=request.company_name,
        tenant_id=ctx.tenant_id,
        customer_id=request.customer_id,
    )
    return _success(result)


@enrichment_router.post("/refresh/{customer_id}")
async def refresh_enrichment(
    customer_id: int = Path(..., ge=1, description="Customer ID to refresh"),
    body: EnrichmentRefreshRequest | None = None,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Re-call the enrichment provider for an existing customer and upsert the record.

    Uses the domain or company_name from the optional request body if provided;
    otherwise falls back to the enrichment data already on record.
    """
    svc = EnrichmentService(session)

    domain_param: str | None = body.domain if body else None
    company_name_param: str | None = body.company_name if body else None

    # If no body, read existing enrichment from DB to get domain/company_name
    if body is None:
        result = await session.execute(
            select(CustomerEnrichmentModel).where(
                and_(
                    CustomerEnrichmentModel.customer_id == customer_id,
                    CustomerEnrichmentModel.tenant_id == ctx.tenant_id,
                )
            ).order_by(CustomerEnrichmentModel.enriched_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raw = existing.raw_data_json or {}
            domain_param = raw.get("domain")
            company_name_param = raw.get("name")

    result = await svc.refresh(
        customer_id=customer_id,
        tenant_id=ctx.tenant_id,
        domain=domain_param,
        company_name=company_name_param,
    )
    return _success(result)
