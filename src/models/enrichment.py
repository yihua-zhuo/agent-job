"""Pydantic request / response schemas for the enrichment API."""

from pydantic import BaseModel, model_validator


class EnrichmentLookupRequest(BaseModel):
    """Request body for ``POST /api/v1/enrichment/lookup``."""

    domain: str | None = None
    company_name: str | None = None

    @model_validator(mode="after")
    def require_exactly_one(self) -> "EnrichmentLookupRequest":
        active = [x for x in (self.domain, self.company_name) if x is not None]
        if len(active) != 1:
            raise ValueError("Provide exactly one of domain or company_name")
        return self
