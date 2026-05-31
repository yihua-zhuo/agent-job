"""Pydantic request / response schemas for the enrichment API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class EnrichmentLookupRequest(BaseModel):
    """Request body for ``POST /api/v1/enrichment/lookup``."""

    customer_id: int
    domain: str | None = None
    company_name: str | None = None

    @model_validator(mode="wrap")
    @classmethod
    def _validate_and_strip(cls, values, handler):
        """Capture raw domain/company_name before strip, then validate."""
        if isinstance(values, dict):
            raw_domain = values.get("domain")
            raw_company_name = values.get("company_name")
            # Strip whitespace from domain/company_name before passing to handler.
            stripped = {**values}
            if stripped.get("domain") is not None:
                stripped["domain"] = stripped["domain"].strip()
            if stripped.get("company_name") is not None:
                stripped["company_name"] = stripped["company_name"].strip()
            instance = handler(stripped)
            # Re-read the original raw values (pre-strip) to decide validation.
            active = [x for x in (raw_domain, raw_company_name) if x is not None and x != ""]
            if len(active) != 1:
                raise ValueError("Provide exactly one of domain or company_name")
            return instance
        return handler(values)

    @field_validator("domain", "company_name")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
        return v


class EnrichmentRefreshRequest(BaseModel):
    """Optional request body for ``POST /api/v1/enrichment/refresh/{customer_id}``."""

    domain: str | None = None
    company_name: str | None = None

    @model_validator(mode="wrap")
    @classmethod
    def _validate_and_strip(cls, values, handler):
        """Capture raw domain/company_name before strip, then validate."""
        if isinstance(values, dict):
            raw_domain = values.get("domain")
            raw_company_name = values.get("company_name")
            # Strip whitespace from domain/company_name before passing to handler.
            stripped = {**values}
            if stripped.get("domain") is not None:
                stripped["domain"] = stripped["domain"].strip()
                stripped["domain"] = stripped["domain"] if stripped["domain"] else None
            if stripped.get("company_name") is not None:
                stripped["company_name"] = stripped["company_name"].strip()
                stripped["company_name"] = stripped["company_name"] if stripped["company_name"] else None
            instance = handler(stripped)
            # Re-read the original raw values (pre-strip) to decide validation.
            active = [x for x in (raw_domain, raw_company_name) if x is not None and x != ""]
            if len(active) == 0:
                raise ValueError("At least one of domain or company_name is required")
            return instance
        return handler(values)

    @field_validator("domain", "company_name")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            v = v if v else None
        return v


class EnrichmentStatusOut(BaseModel):
    """Enrichment status fields used to augment customer responses.

    Defined here so the shape is explicit and documented rather than implicit.
    Used as documentation/reference in CustomerModel response schemas.
    """

    model_config = ConfigDict(populate_by_name=True)

    enrichment_status: Literal["none", "enriched", "stale"]
    last_enriched_at: datetime | None = None
