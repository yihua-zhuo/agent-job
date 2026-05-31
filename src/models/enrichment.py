"""Pydantic request / response schemas for the enrichment API."""

from pydantic import BaseModel, field_validator, model_validator


class EnrichmentLookupRequest(BaseModel):
    """Request body for ``POST /api/v1/enrichment/lookup``."""

    customer_id: int
    domain: str | None = None
    company_name: str | None = None

    @field_validator("domain", "company_name")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
        return v

    @model_validator(mode="after")
    def require_exactly_one(self) -> "EnrichmentLookupRequest":
        # Use raw (pre-validator) values so '' is distinguishable from absent.
        # __pydantic_extra__ is avoided; access via object.__dict__ to bypass the
        # to-python strip that the field validator already applied.
        raw_domain: str | None = object.__getattribute__(self, "domain")
        raw_name: str | None = object.__getattribute__(self, "company_name")
        # Restore stripped value for the active check.
        active = [
            x.strip() if isinstance(x, str) else None
            for x in (raw_domain, raw_name)
            if x is not None and x != ""
        ]
        if len(active) != 1:
            raise ValueError("Provide exactly one of domain or company_name")
        return self
