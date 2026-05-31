"""Enrichment API router — ``POST /api/v1/enrichment/lookup`` and ``POST /api/v1/enrichment/refresh/{customer_id}``."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Path
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models.customer import CustomerModel
from db.models.customer_enrichment import CustomerEnrichmentModel
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.enrichment import EnrichmentLookupRequest, EnrichmentRefreshRequest
from pkg.errors.app_exceptions import NotFoundException, ValidationException
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

    # Default to no prior enrichment; populate from DB only when body is absent
    existing_enrichment = None

    if body is None:
        result = await session.execute(
            select(CustomerEnrichmentModel)
            .where(
                and_(
                    CustomerEnrichmentModel.customer_id == customer_id,
                    CustomerEnrichmentModel.tenant_id == ctx.tenant_id,
                )
            )
            .order_by(CustomerEnrichmentModel.enriched_at.desc())
            .limit(1)
        )
        existing_enrichment = result.scalar_one_or_none()

    domain_param: str | None = body.domain if body else None
    company_name_param: str | None = body.company_name if body else None

    if body is None and existing_enrichment is not None:
        raw = existing_enrichment.raw_data_json or {}
        domain_param = raw.get("domain")
        company_name_param = raw.get("name")

    # Guard: if stored values are empty strings, don't call the provider with them.
    if not domain_param:
        domain_param = None
    if not company_name_param:
        company_name_param = None

    if domain_param is None and company_name_param is None:
        raise ValidationException("domain or company_name is required when customer has no prior enrichment record")

    # Verify the customer belongs to this tenant before calling the service.
    customer_result = await session.execute(
        select(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == ctx.tenant_id))
    )
    if customer_result.scalar_one_or_none() is None:
        raise NotFoundException("Customer")

    result, _raw_data = await svc.refresh(
        customer_id=customer_id,
        tenant_id=ctx.tenant_id,
        domain=domain_param,
        company_name=company_name_param,
    )
    # _raw_data not needed in response — only normalised data is returned

    # Re-fetch the upserted record to derive status from next_refresh_at.
    upserted_result = await session.execute(
        select(CustomerEnrichmentModel)
        .where(
            and_(
                CustomerEnrichmentModel.customer_id == customer_id,
                CustomerEnrichmentModel.tenant_id == ctx.tenant_id,
            )
        )
        .order_by(CustomerEnrichmentModel.enriched_at.desc())
        .limit(1)
    )
    upserted = upserted_result.scalar_one_or_none()

    data = dict(result)
    if upserted is not None:
        data["last_enriched_at"] = upserted.enriched_at.isoformat() if upserted.enriched_at else None
        if upserted.next_refresh_at is not None and upserted.next_refresh_at <= datetime.now(UTC):
            data["enrichment_status"] = "stale"
        else:
            data["enrichment_status"] = "enriched"
    else:
        # Consistency problem: upsert reported success but the record is gone.
        data["last_enriched_at"] = None
        data["enrichment_status"] = "none"

    return _success(data)
