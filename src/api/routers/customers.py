"""Customer router — all /api/v1/customers endpoints."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from pkg.response.schemas import (
    BulkImportResponse,
    CustomerData,
    CustomerListData,
    CustomerListResponse,
    CustomerResponse,
    CustomerSearchData,
    CustomerSearchResponse,
    ErrorEnvelope,
    OwnerChangeResponse,
    StatusChangeResponse,
    TagResponse,
)
from services.customer_service import CustomerService

customers_router = APIRouter(prefix='/api/v1/customers', tags=['customers'])


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def _sanitize(s: str) -> str:
    if not s:
        return s
    # Remove matched tag pairs with their content first (e.g. <script>...)</n    # Use case-insensitive flag so <SCRIPT> is also stripped
    s = re.sub(r'<(script)[^>]*>.*?</\1>', '', s, flags=re.DOTALL | re.IGNORECASE)
    # Now remove any remaining tags
    s = re.sub(r'<[^>]*>', '', s)
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()


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
# Request schemas (requirement 9 — Field constraints)
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="客户名称")
    email: str | None = Field(None, max_length=255, description="邮箱")
    phone: str | None = Field(None, max_length=50, description="电话")
    company: str | None = Field(None, max_length=200, description="公司")
    status: str | None = Field(default='lead', pattern="^(lead|customer|partner|prospect)$")
    owner_id: int | None = Field(default=0, ge=0, description="负责人 ID")
    tags: list[str] | None = Field(default_factory=list, description="标签列表")

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
    tag: str = Field(..., min_length=1, max_length=100)


class StatusChange(BaseModel):
    status: str = Field(..., pattern="^(active|inactive|blocked)$")


class OwnerChange(BaseModel):
    owner_id: int = Field(..., ge=0)


class BulkImport(BaseModel):
    customers: list[dict] = Field(..., max_length=1000)


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@customers_router.post(
    '',
    status_code=201,
    response_model=CustomerResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_customer(
    body: CustomerCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.create_customer(body.model_dump(), tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return CustomerResponse(message=resp.message, data=CustomerData.model_validate(resp.data))


@customers_router.get(
    '',
    response_model=CustomerListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    owner_id: int | None = Query(None, ge=0),
    tags: str | None = None,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.list_customers(
        page=page, page_size=page_size, status=status,
        owner_id=owner_id, tags=tags, tenant_id=ctx.tenant_id,
    )
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    _is_dict = isinstance(resp.data, dict)
    if _is_dict:
        _items = resp.data["items"]
        _total = resp.data["total"]
        _page = resp.data["page"]
        _page_size = resp.data["page_size"]
        _total_pages = resp.data["total_pages"]
        _has_next = resp.data["has_next"]
        _has_prev = resp.data["has_prev"]
    else:
        _items = resp.data.items
        _total = resp.data.total
        _page = resp.data.page
        _page_size = resp.data.page_size
        _total_pages = resp.data.total_pages
        _has_next = resp.data.has_next
        _has_prev = resp.data.has_prev
    items = [CustomerData.model_validate({**c, "tags": c.get("tags") or []}) for c in _items]
    return CustomerListResponse(
        message=resp.message,
        data=CustomerListData(
            items=items,
            total=_total,
            page=_page,
            page_size=_page_size,
            total_pages=_total_pages,
            has_next=_has_next,
            has_prev=_has_prev,
        ),
    )


@customers_router.get(
    '/search',
    response_model=CustomerSearchResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def search_customers(
    keyword: str = Query('', max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.search_customers(_sanitize(keyword), tenant_id=ctx.tenant_id)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    _items = getattr(resp.data, "items", None)
    if _items is None or callable(_items):
        _items = resp.data["items"]
    items = [CustomerData.model_validate({**c, "tags": c.get("tags") or []}) for c in _items]
    return CustomerSearchResponse(
        message=resp.message,
        data=CustomerSearchData(
            keyword=resp.data["keyword"],
            items=items,
        ),
    )


@customers_router.get(
    '/{customer_id}',
    response_model=CustomerResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def get_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return CustomerResponse(message=resp.message, data=CustomerData.model_validate(resp.data))


@customers_router.put(
    '/{customer_id}',
    response_model=CustomerResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def update_customer(
    customer_id: int,
    body: dict,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.update_customer(customer_id, body, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    if resp.data:
        return CustomerResponse(message=resp.message, data=CustomerData.model_validate(resp.data))
    return CustomerResponse(message=resp.message, data=None)


@customers_router.delete(
    '/{customer_id}',
    response_model=CustomerResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def delete_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.delete_customer(customer_id, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return CustomerResponse(message=resp.message, data=None)


@customers_router.post(
    '/{customer_id}/tags',
    response_model=TagResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def add_tag(
    customer_id: int,
    body: TagOp,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.add_tag(customer_id, _sanitize(body.tag), tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return TagResponse(
        message=resp.message,
        data={"id": customer_id, "tag": body.tag},
    )


@customers_router.delete(
    '/{customer_id}/tags/{tag}',
    response_model=TagResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def remove_tag(
    customer_id: int,
    tag: str,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.remove_tag(customer_id, _sanitize(tag), tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return TagResponse(
        message=resp.message,
        data={"id": customer_id, "tag": tag},
    )


@customers_router.put(
    '/{customer_id}/status',
    response_model=StatusChangeResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def change_status(
    customer_id: int,
    body: StatusChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.change_status(customer_id, body.status, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return StatusChangeResponse(message=resp.message, data=resp.data)


@customers_router.put(
    '/{customer_id}/owner',
    response_model=OwnerChangeResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def assign_owner(
    customer_id: int,
    body: OwnerChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    resp = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return OwnerChangeResponse(message=resp.message, data=resp.data)


@customers_router.post(
    '/import',
    response_model=BulkImportResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def bulk_import(
    body: BulkImport,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    if len(body.customers) > 1000:
        raise HTTPException(status_code=400, detail='Maximum 1000 customers per import')
    service = CustomerService(session)
    resp = await service.bulk_import(body.customers, tenant_id=ctx.tenant_id)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return BulkImportResponse(message=resp.message, data=resp.data)
