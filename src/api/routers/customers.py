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
from services.customer_service import CustomerService
from services.lead_routing_service import LeadRoutingService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


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
    status: str | None = Field(default="lead", pattern="^(lead|customer|partner|prospect)$")
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
    status: str = Field(..., pattern="^(active|inactive|blocked)$")


class OwnerChange(BaseModel):
    owner_id: int = Field(..., ge=0)


class BulkImport(BaseModel):
    customers: list[dict] = Field(..., max_length=1000)


class ManualAssign(BaseModel):
    owner_id: int = Field(..., ge=0)
    reason: str | None = Field(None, max_length=500)


class ReassignLead(BaseModel):
    new_owner_id: int = Field(..., ge=0)
    reason: str | None = Field(None, max_length=500)


class ManualRecycle(BaseModel):
    customer_ids: list[int] = Field(..., min_length=1)


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


# ---------------------------------------------------------------------------
# Lead distribution endpoints (sales team view)
# ---------------------------------------------------------------------------


@customers_router.get("/leads")
async def list_sales_leads(
    status: str = Query("unassigned", pattern="^(unassigned|assigned|recycled)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Unassigned leads queue for the sales team."""
    service = CustomerService(session)
    routing_svc = LeadRoutingService(session)

    if status == "unassigned":
        items, total = await service.get_unassigned_leads(ctx.tenant_id, page=page, page_size=page_size)
    elif status == "assigned":
        items, total = await service.get_leads_by_owner(ctx.user_id, ctx.tenant_id, page=page, page_size=page_size)
    else:  # recycled
        from sqlalchemy import and_, func, select

        from db.models.customer import CustomerModel

        conditions = and_(
            CustomerModel.tenant_id == ctx.tenant_id,
            CustomerModel.status == "lead",
            CustomerModel.recycle_count > 0,
        )
        count_result = await session.execute(
            select(func.count(CustomerModel.id)).where(conditions)
        )
        total = count_result.scalar() or 0

        result = await session.execute(
            select(CustomerModel)
            .where(conditions)
            .order_by(CustomerModel.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = result.scalars().all()

    enriched = []
    for lead in items:
        d = lead.to_dict()
        d["sla_status"] = routing_svc.get_sla_status(lead.assigned_at)
        enriched.append(d)

    total_pages = math.ceil(total / page_size) if page_size else 0
    return {
        "success": True,
        "data": {
            "items": enriched,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@customers_router.get("/{customer_id}/assignment")
async def get_customer_assignment(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Current assignment info for a customer."""
    service = CustomerService(session)
    routing_svc = LeadRoutingService(session)
    customer = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    sla = routing_svc.get_sla_status(customer.assigned_at)

    # Fetch assigned user name if owner_id != 0
    assigned_to_name = None
    if customer.owner_id and customer.owner_id > 0:
        from sqlalchemy import and_, select

        from db.models.user import UserModel

        user_result = await session.execute(
            select(UserModel.full_name).where(
                and_(UserModel.id == customer.owner_id, UserModel.tenant_id == ctx.tenant_id)
            )
        )
        assigned_to_name = user_result.scalar_one_or_none()

    return {
        "success": True,
        "data": {
            "customer_id": customer.id,
            "assigned_to": customer.owner_id,
            "assigned_to_name": assigned_to_name,
            "assigned_at": customer.assigned_at.isoformat() if customer.assigned_at else None,
            "sla_status": sla,
            "recycle_count": customer.recycle_count or 0,
            "recycle_history": customer.recycle_history or [],
        },
    }


@customers_router.post("/{customer_id}/assign")
async def manual_assign_customer(
    customer_id: int,
    body: ManualAssign,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Manually assign a customer to an owner, bypassing routing rules."""
    service = CustomerService(session)
    result = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "负责人分配成功"}


@customers_router.post("/{customer_id}/reassign")
async def reassign_lead(
    customer_id: int,
    body: ReassignLead,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Reassign a lead with reason logged to recycle_history."""
    service = CustomerService(session)
    result = await service.reassign_lead(
        customer_id,
        body.new_owner_id,
        tenant_id=ctx.tenant_id,
        reason=body.reason,
    )
    return {"success": True, "data": result.to_dict(), "message": "负责人变更成功"}


@customers_router.post("/leads/recycle")
async def trigger_lead_recycle(
    body: ManualRecycle,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Manually trigger lead recycle (admin/manager only)."""
    if "admin" not in ctx.roles and "manager" not in ctx.roles:
        from pkg.errors.app_exceptions import ForbiddenException

        raise ForbiddenException("需要 admin 或 manager 角色")
    service = CustomerService(session)
    recycled = await service.bulk_recycle(body.customer_ids, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {"recycled_ids": recycled},
        "message": f"已回收 {len(recycled)} 个线索",
    }
