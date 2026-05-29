"""Pydantic request / response schemas for the enrichment API."""

from pydantic import BaseModel


class EnrichmentLookupRequest(BaseModel):
    """Request body for ``POST /api/v1/enrichment/lookup``."""

    domain: str | None = None
    company_name: str | None = None
