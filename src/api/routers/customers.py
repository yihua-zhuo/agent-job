"""Customer router — all /api/v1/customers endpoints.

Services raise AppException subclasses on errors (caught by global handler in main.py).
Router wraps successful returns in {"success": True, "data": ...} dicts.
"""

import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.customer import CustomerStatus
from services.customer_service import CustomerService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])
CUSTOMER_STATUS_PATTERN = "^(" + "|".join(re.escape(status.value) for status in CustomerStatus) + ")$"
STATUS_CHANGE_PATTERN = "^(active|inactive|blocked)$"


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


def _sanitize(s: str) -> str:
    if not s:
        return s
    # Remove matched tag pairs with their content first (e.g. <script>...)
    # Use case-insensitive flag so <SCRIPT> is also stripped
    s = re.sub(r"<(script)[^>]*>.*?</\1>", "", s, flags=re.DOTALL | re.IGNORECASE)
    # Now remove any remaining tags
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", s)
    return s.strip()


def _paginated(items, total, page, page_size):
    total_pages = math.ceil(total / page_size) if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas (requirement 9 — Field constraints)
# ---------------------------------------------------------------------------


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="客户名称")
    email: str | None = Field(None, max_length=255, description="邮箱")
    phone: str | None = Field(None, max_length=50, description="电话")
    company: str | None = Field(None, max_length=200, description="公司")
    status: str | None = Field(default="lead", pattern=CUSTOMER_STATUS_PATTERN)
    owner_id: int | None = Field(default=0, ge=0, description="负责人 ID")
    tags: list[str] | None = Field(default_factory=list, description="标签列表")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("客户名称不能为空")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        if v and not _is_valid_email(v):
            raise ValueError("邮箱格式不正确")
        return v


class TagOp(BaseModel):
    tag: str = Field(..., min_length=1, max_length=100)


class StatusChange(BaseModel):
    status: str = Field(..., pattern=STATUS_CHANGE_PATTERN)


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


@customers_router.post("", status_code=201)
async def create_customer(
    body: CustomerCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.create_customer(body.model_dump(), tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "客户创建成功"}


@customers_router.get("")
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
    items, total = await service.list_customers(
        page=page,
        page_size=page_size,
        status=status,
        owner_id=owner_id,
        tags=tags,
        tenant_id=ctx.tenant_id,
    )
    return _paginated(items, total, page, page_size)


@customers_router.get("/search")
async def search_customers(
    keyword: str = Query("", max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    items = await service.search_customers(_sanitize(keyword), tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"keyword": keyword, "items": items}}


@customers_router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}


@customers_router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: dict,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.update_customer(customer_id, body, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "客户更新成功"}


@customers_router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.delete_customer(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "客户删除成功"}


@customers_router.post("/{customer_id}/tags")
async def add_tag(
    customer_id: int,
    body: TagOp,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.add_tag(customer_id, _sanitize(body.tag), tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "标签添加成功"}


@customers_router.delete("/{customer_id}/tags/{tag}")
async def remove_tag(
    customer_id: int,
    tag: str,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.remove_tag(customer_id, _sanitize(tag), tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "标签移除成功"}


@customers_router.put("/{customer_id}/status")
async def change_status(
    customer_id: int,
    body: StatusChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.change_status(customer_id, body.status, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "状态更新成功"}


@customers_router.put("/{customer_id}/owner")
async def assign_owner(
    customer_id: int,
    body: OwnerChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = CustomerService(session)
    result = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "负责人更新成功"}


@customers_router.post("/import")
async def bulk_import(
    body: BulkImport,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    if len(body.customers) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 customers per import")
    service = CustomerService(session)
    imported_count = await service.bulk_import(body.customers, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"imported": imported_count}, "message": "批量导入成功"}
