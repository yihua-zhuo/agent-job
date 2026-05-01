"""FastAPI routes - /api/v1/customers, /api/v1/sales/pipelines, /api/v1/sales/opportunities"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re

from src.internal.middleware.fastapi_auth import require_auth, get_current_tenant_id, AuthContext
from src.services.customer_service import CustomerService
from src.services.sales_service import SalesService
from src.models.response import ResponseStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


def _validate_pagination(page: int, page_size: int):
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def _sanitize(s: str) -> str:
    if not s:
        return s
    s = re.sub(r'<[^>]*>', '', s)
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = 'lead'
    owner_id: Optional[int] = 0
    tags: Optional[List[str]] = []

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('客户名称不能为空')
        return v.strip()

    @field_validator('email')
    @classmethod
    def email_format(cls, v):
        if v and not _is_valid_email(v):
            raise ValueError('邮箱格式不正确')
        return v


class TagOp(BaseModel):
    tag: str


class StatusChange(BaseModel):
    status: str


class OwnerChange(BaseModel):
    owner_id: int


class BulkImport(BaseModel):
    customers: List[dict]


class OpportunityCreate(BaseModel):
    name: str
    customer_id: int
    pipeline_id: int
    stage: str
    amount: float
    owner_id: int
    close_date: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('name', 'stage')
    @classmethod
    def not_empty(cls, v, info):
        if not v or not v.strip():
            raise ValueError(f'{info.name}不能为空')
        return v.strip()


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    customer_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    stage: Optional[str] = None
    amount: Optional[float] = None
    owner_id: Optional[int] = None
    close_date: Optional[str] = None
    notes: Optional[str] = None


class PipelineCreate(BaseModel):
    name: str
    is_default: Optional[bool] = False
    stages: Optional[List[str]] = None

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('管道名称不能为空')
        return v.strip()


class StageChange(BaseModel):
    stage: str


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

customers_router = APIRouter(prefix='/api/v1/customers', tags=['customers'])
sales_router = APIRouter(prefix='/api/v1/sales', tags=['sales'])


# ---------------------------------------------------------------------------
# Customer endpoints
# ---------------------------------------------------------------------------

@customers_router.post('', status_code=201)
async def create_customer(
    body: CustomerCreate,
    request: Request,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    data = body.model_dump()
    resp = await service.create_customer(data, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.get('')
async def list_customers(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    owner_id: Optional[int] = None,
    tags: Optional[str] = None,
    ctx: AuthContext = Depends(require_auth),
):
    _validate_pagination(page, page_size)
    service = CustomerService()
    resp = await service.list_customers(
        page=page, page_size=page_size, status=status,
        owner_id=owner_id, tags=tags, tenant_id=ctx.tenant_id,
    )
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.get('/search')
async def search_customers(
    keyword: str = Query('', max_length=200),
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.search_customers(_sanitize(keyword), tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.get('/{customer_id}')
async def get_customer(
    customer_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.put('/{customer_id}')
async def update_customer(
    customer_id: int,
    body: dict,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.update_customer(customer_id, body, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.delete('/{customer_id}')
async def delete_customer(
    customer_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.delete_customer(customer_id, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.post('/{customer_id}/tags')
async def add_tag(
    customer_id: int,
    body: TagOp,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.add_tag(customer_id, _sanitize(body.tag), tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.delete('/{customer_id}/tags/{tag}')
async def remove_tag(
    customer_id: int,
    tag: str,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.remove_tag(customer_id, _sanitize(tag), tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.put('/{customer_id}/status')
async def change_status(
    customer_id: int,
    body: StatusChange,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    valid = ['active', 'inactive', 'blocked']
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f'status must be one of: {valid}')
    service = CustomerService()
    resp = await service.change_status(customer_id, body.status, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.put('/{customer_id}/owner')
async def assign_owner(
    customer_id: int,
    body: OwnerChange,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = CustomerService()
    resp = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@customers_router.post('/import')
async def bulk_import(
    body: BulkImport,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    if len(body.customers) > 1000:
        raise HTTPException(status_code=400, detail='Maximum 1000 customers per import')
    service = CustomerService()
    resp = await service.bulk_import(body.customers, tenant_id=ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


# ---------------------------------------------------------------------------
# Sales / Pipeline endpoints
# ---------------------------------------------------------------------------

@sales_router.post('/pipelines', status_code=201)
async def create_pipeline(
    body: PipelineCreate,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    data = body.model_dump()
    resp = await service.create_pipeline(ctx.tenant_id, data)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/pipelines')
async def list_pipelines(
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.list_pipelines(ctx.tenant_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/pipelines/{pipeline_id}')
async def get_pipeline(
    pipeline_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.get_pipeline(ctx.tenant_id, pipeline_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/pipelines/{pipeline_id}/stats')
async def get_pipeline_stats(
    pipeline_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.get_pipeline_stats(ctx.tenant_id, pipeline_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/pipelines/{pipeline_id}/funnel')
async def get_pipeline_funnel(
    pipeline_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.get_pipeline_funnel(ctx.tenant_id, pipeline_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


# ---------------------------------------------------------------------------
# Sales / Opportunity endpoints
# ---------------------------------------------------------------------------

@sales_router.post('/opportunities', status_code=201)
async def create_opportunity(
    body: OpportunityCreate,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    data = body.model_dump()
    resp = await service.create_opportunity(ctx.tenant_id, data)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/opportunities')
async def list_opportunities(
    request: Request = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline_id: Optional[int] = None,
    stage: Optional[str] = None,
    owner_id: Optional[int] = None,
    ctx: AuthContext = Depends(require_auth),
):
    _validate_pagination(page, page_size)
    service = SalesService()
    resp = await service.list_opportunities(
        ctx.tenant_id, page=page, page_size=page_size,
        pipeline_id=pipeline_id, stage=stage, owner_id=owner_id,
    )
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/opportunities/{opp_id}')
async def get_opportunity(
    opp_id: int,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.get_opportunity(ctx.tenant_id, opp_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.put('/opportunities/{opp_id}')
async def update_opportunity(
    opp_id: int,
    body: OpportunityUpdate,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    data = body.model_dump(exclude_none=True)
    resp = await service.update_opportunity(ctx.tenant_id, opp_id, data)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.put('/opportunities/{opp_id}/stage')
async def change_stage(
    opp_id: int,
    body: StageChange,
    request: Request = None,
    ctx: AuthContext = Depends(require_auth),
):
    if not body.stage or not body.stage.strip():
        raise HTTPException(status_code=400, detail='stage is required')
    service = SalesService()
    resp = await service.change_stage(ctx.tenant_id, opp_id, body.stage.strip())
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))


@sales_router.get('/forecast')
async def get_forecast(
    request: Request = None,
    owner_id: Optional[int] = None,
    ctx: AuthContext = Depends(require_auth),
):
    service = SalesService()
    resp = await service.get_forecast(ctx.tenant_id, owner_id=owner_id)
    return JSONResponse(content=resp.to_dict(), status_code=_http_status(resp.status))