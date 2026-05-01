"""Standardized API response envelopes — requirement 7.

Concrete typed response schemas — one per endpoint shape.
Each schema documents the exact data structure Swagger will display.
"""
from datetime import datetime
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, Field


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Base envelope (used by all responses)
# ---------------------------------------------------------------------------

class SuccessEnvelope(BaseModel):
    """Shared envelope fields — all API responses inherit these."""
    success: bool = True
    message: str = "OK"


class ErrorEnvelope(BaseModel):
    """Error envelope — used when the HTTP status code is >= 400."""
    success: bool = False
    message: str


# ---------------------------------------------------------------------------
# Generic base (kept for generic helpers / internal use)
# ---------------------------------------------------------------------------

class APIResponse(BaseModel, Generic[T]):
    """Single-item response envelope."""
    success: bool = True
    message: str = "OK"
    data: Optional[T] = None

    @classmethod
    def ok(cls, data: T, message: str = "OK") -> "APIResponse[T]":
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str) -> "APIResponse[None]":
        return cls(success=False, message=message, data=None)


# ---------------------------------------------------------------------------
# Customer schemas
# ---------------------------------------------------------------------------

class CustomerData(BaseModel):
    """Fields returned for a single customer."""
    id: int
    tenant_id: int
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=200)
    status: str = Field(..., pattern="^(lead|customer|partner|prospect|active|inactive|blocked)$")
    owner_id: int = Field(..., ge=0)
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerSearchData(BaseModel):
    """Non-paginated search result data field."""
    keyword: str
    items: List[CustomerData]


class CustomerSearchResponse(SuccessEnvelope):
    """GET /search — keyword search without pagination."""
    data: CustomerSearchData


class CustomerListData(BaseModel):
    """Paginated customer list data field."""
    items: List[CustomerData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class CustomerResponse(SuccessEnvelope):
    """POST /customers · GET /{id} — single customer."""
    data: Optional[CustomerData] = None


class CustomerListResponse(SuccessEnvelope):
    """GET /customers — paginated customer list."""
    data: CustomerListData


class TagData(BaseModel):
    id: int
    tag: str


class TagResponse(SuccessEnvelope):
    """POST /{id}/tags · DELETE /{id}/tags/{tag}."""
    data: Optional[TagData] = None


class IdData(BaseModel):
    id: int
    status: Optional[str] = None
    owner_id: Optional[int] = None


class StatusChangeResponse(SuccessEnvelope):
    """PUT /{id}/status."""
    data: Optional[IdData] = None


class OwnerChangeResponse(SuccessEnvelope):
    """PUT /{id}/owner."""
    data: Optional[IdData] = None


class BulkImportData(BaseModel):
    imported: int = Field(..., ge=0)
    errors: List[dict] = Field(default_factory=list)


class BulkImportResponse(SuccessEnvelope):
    """POST /import."""
    data: BulkImportData


# ---------------------------------------------------------------------------
# Pipeline schemas
# ---------------------------------------------------------------------------

class PipelineData(BaseModel):
    """Fields returned for a single pipeline."""
    id: int
    tenant_id: int
    name: str = Field(..., min_length=1, max_length=200)
    stages: List[str]
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineListData(BaseModel):
    items: List[PipelineData]
    total: int = Field(..., ge=0)


class PipelineStatsData(BaseModel):
    pipeline_id: int
    total: int = Field(..., ge=0)
    won: int = Field(..., ge=0)
    lost: int = Field(..., ge=0)


class PipelineFunnelData(BaseModel):
    pipeline_id: int
    stages: List[dict]


class PipelineResponse(SuccessEnvelope):
    """POST /pipelines · GET /pipelines/{id}."""
    data: Optional[PipelineData] = None


class PipelineListResponse(SuccessEnvelope):
    """GET /pipelines."""
    data: PipelineListData


class PipelineStatsResponse(SuccessEnvelope):
    """GET /pipelines/{id}/stats."""
    data: PipelineStatsData


class PipelineFunnelResponse(SuccessEnvelope):
    """GET /pipelines/{id}/funnel."""
    data: PipelineFunnelData


# ---------------------------------------------------------------------------
# Opportunity schemas
# ---------------------------------------------------------------------------

class OpportunityData(BaseModel):
    """Fields returned for a single opportunity."""
    id: int
    tenant_id: int
    name: str
    customer_id: int
    pipeline_id: int
    stage: str
    amount: str
    probability: int = Field(..., ge=0, le=100)
    expected_close_date: Optional[str] = None
    owner_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OpportunityListData(BaseModel):
    items: List[OpportunityData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class OpportunityResponse(SuccessEnvelope):
    """POST /opportunities · GET /{id}."""
    data: Optional[OpportunityData] = None


class OpportunityListResponse(SuccessEnvelope):
    """GET /opportunities."""
    data: OpportunityListData


class StageChangeData(BaseModel):
    id: int
    stage: str


class StageChangeResponse(SuccessEnvelope):
    """PUT /opportunities/{id}/stage."""
    data: StageChangeData


# ---------------------------------------------------------------------------
# Forecast schemas
# ---------------------------------------------------------------------------

class OwnerForecastData(BaseModel):
    owner_id: int
    forecast: dict


class ForecastData(BaseModel):
    owner_id: Optional[int] = None
    forecast: dict


class ForecastResponse(SuccessEnvelope):
    """GET /forecast."""
    data: ForecastData
