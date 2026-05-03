"""Tenants router — /api/v1/tenants endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth, AuthContext
from services.tenant_service import TenantService
from models.response import ResponseStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope

tenants_router = APIRouter(prefix='/api/v1/tenants', tags=['tenants'])


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


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field(..., min_length=1, max_length=50)
    admin_email: Optional[str] = Field(None, max_length=255)
    settings: Optional[dict] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    plan: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[str] = None
    settings: Optional[dict] = None


class TenantData(BaseModel):
    id: int
    name: str
    plan: str
    status: str
    settings: dict = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TenantResponse(SuccessEnvelope):
    data: Optional[TenantData] = None


class TenantListData(BaseModel):
    items: List[TenantData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class TenantListResponse(SuccessEnvelope):
    data: TenantListData


class TenantStatsData(BaseModel):
    tenant_id: int
    user_count: int
    storage_used: int
    api_calls: int


class TenantStatsResponse(SuccessEnvelope):
    data: TenantStatsData


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@tenants_router.post(
    '',
    status_code=201,
    response_model=TenantResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_tenant(
    body: TenantCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.create_tenant(
        name=body.name,
        plan=body.plan,
        admin_email=body.admin_email,
        **( {"settings": body.settings} if body.settings else {} ),
    )
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantResponse(message=resp.message, data=TenantData(**resp.data))


@tenants_router.get(
    '/stats',
    response_model=TenantStatsResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_tenant_stats(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.get_tenant_stats(ctx.tenant_id)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantStatsResponse(message=resp.message, data=TenantStatsData(**resp.data))


@tenants_router.get(
    '/usage',
    response_model=TenantStatsResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_tenant_usage(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.get_tenant_usage(ctx.tenant_id)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantStatsResponse(message=resp.message, data=TenantStatsData(**resp.data))


@tenants_router.get(
    '/{tenant_id}',
    response_model=TenantResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def get_tenant(
    tenant_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.get_tenant(tenant_id)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantResponse(message=resp.message, data=TenantData(**resp.data))


@tenants_router.get(
    '',
    response_model=TenantListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.list_tenants(page=page, page_size=page_size)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    items = [TenantData(**t) for t in resp.data.items]
    total_pages = (resp.data.total + resp.data.page_size - 1) // resp.data.page_size if resp.data.page_size > 0 else 0
    return TenantListResponse(
        message=resp.message,
        data=TenantListData(
            items=items,
            total=resp.data.total,
            page=resp.data.page,
            page_size=resp.data.page_size,
            total_pages=total_pages,
            has_next=resp.data.page < total_pages,
            has_prev=resp.data.page > 1,
        ),
    )


@tenants_router.put(
    '/{tenant_id}',
    response_model=TenantResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def update_tenant(
    tenant_id: int,
    body: TenantUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    update_data = body.model_dump(exclude_none=True)
    resp = await service.update_tenant(tenant_id, **update_data)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantResponse(message=resp.message, data=TenantData(**resp.data))


@tenants_router.delete(
    '/{tenant_id}',
    response_model=TenantResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def delete_tenant(
    tenant_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TenantService(session)
    resp = await service.delete_tenant(tenant_id)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return TenantResponse(message=resp.message, data=resp.data)