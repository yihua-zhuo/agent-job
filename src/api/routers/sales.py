"""Sales router — /api/v1/sales/pipelines, /api/v1/sales/opportunities, /api/v1/sales/forecast."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth, AuthContext
from services.sales_service import SalesService


sales_router = APIRouter(prefix='/api/v1/sales', tags=['sales'])


# ---------------------------------------------------------------------------
# Request schemas (requirement 9 — Field constraints)
# ---------------------------------------------------------------------------

class OpportunityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="商机名称")
    customer_id: int = Field(..., ge=1, description="客户 ID")
    pipeline_id: int = Field(..., ge=1, description="管道 ID")
    stage: str = Field(..., min_length=1, max_length=50, description="阶段")
    amount: float = Field(..., ge=0, description="金额")
    owner_id: int = Field(..., ge=0, description="负责人 ID")
    close_date: Optional[str] = Field(None, description="预计关闭日期 ISO 格式")
    notes: Optional[str] = Field(None, max_length=2000, description="备注")


class OpportunityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    customer_id: Optional[int] = Field(None, ge=1)
    pipeline_id: Optional[int] = Field(None, ge=1)
    stage: Optional[str] = Field(None, min_length=1, max_length=50)
    amount: Optional[float] = Field(None, ge=0)
    owner_id: Optional[int] = Field(None, ge=0)
    close_date: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)


class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="管道名称")
    is_default: Optional[bool] = Field(default=False, description="是否默认管道")
    stages: Optional[List[str]] = Field(default=None, description="阶段列表")


class StageChange(BaseModel):
    stage: str = Field(..., min_length=1, max_length=50)


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Generic API response wrapper
# ---------------------------------------------------------------------------

class ApiDataResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
    errors: Optional[List[dict]] = None


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

@sales_router.post('/pipelines', status_code=201, response_model=ApiDataResponse)
async def create_pipeline(
    body: PipelineCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.create_pipeline(ctx.tenant_id, body.model_dump())
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/pipelines', response_model=ApiDataResponse)
async def list_pipelines(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.list_pipelines(ctx.tenant_id)
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/pipelines/{pipeline_id}', response_model=ApiDataResponse)
async def get_pipeline(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.get_pipeline(ctx.tenant_id, pipeline_id)
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/pipelines/{pipeline_id}/stats', response_model=ApiDataResponse)
async def get_pipeline_stats(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.get_pipeline_stats(ctx.tenant_id, pipeline_id)
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/pipelines/{pipeline_id}/funnel', response_model=ApiDataResponse)
async def get_pipeline_funnel(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.get_pipeline_funnel(ctx.tenant_id, pipeline_id)
    return ApiDataResponse(**resp.to_dict())


# ---------------------------------------------------------------------------
# Opportunity endpoints
# ---------------------------------------------------------------------------

@sales_router.post('/opportunities', status_code=201, response_model=ApiDataResponse)
async def create_opportunity(
    body: OpportunityCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    data = body.model_dump()
    data['expected_close_date'] = data.pop('close_date', None)
    resp = await service.create_opportunity(ctx.tenant_id, data)
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/opportunities', response_model=ApiDataResponse)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline_id: Optional[int] = None,
    stage: Optional[str] = None,
    owner_id: Optional[int] = None,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.list_opportunities(
        ctx.tenant_id, page=page, page_size=page_size,
        pipeline_id=pipeline_id, stage=stage, owner_id=owner_id,
    )
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/opportunities/{opp_id}', response_model=ApiDataResponse)
async def get_opportunity(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.get_opportunity(ctx.tenant_id, opp_id)
    return ApiDataResponse(**resp.to_dict())


@sales_router.put('/opportunities/{opp_id}', response_model=ApiDataResponse)
async def update_opportunity(
    opp_id: int,
    body: OpportunityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    data = body.model_dump(exclude_none=True)
    if 'close_date' in data:
        data['expected_close_date'] = data.pop('close_date')
    resp = await service.update_opportunity(ctx.tenant_id, opp_id, data)
    return ApiDataResponse(**resp.to_dict())


@sales_router.put('/opportunities/{opp_id}/stage', response_model=ApiDataResponse)
async def change_stage(
    opp_id: int,
    body: StageChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.change_stage(ctx.tenant_id, opp_id, body.stage)
    return ApiDataResponse(**resp.to_dict())


@sales_router.get('/forecast', response_model=ApiDataResponse)
async def get_forecast(
    owner_id: Optional[int] = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = SalesService(session)
    resp = await service.get_forecast(ctx.tenant_id, owner_id=owner_id)
    return ApiDataResponse(**resp.to_dict())