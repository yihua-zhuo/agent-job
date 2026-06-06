"""Customer router — all /api/v1/customers endpoints.

Services raise AppException subclasses on errors (caught by global handler in main.py).
Router wraps successful returns in {"success": True, "data": ...} dicts.
"""

import math
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models.customer import CustomerModel
from db.models.customer_enrichment import CustomerEnrichmentModel
from db.repositories import CustomerRepository
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.customer import CustomerStatus
from pkg.errors.app_exceptions import ForbiddenException, NotFoundException
from services.customer_service import CustomerService
from services.lead_routing_service import LeadRoutingService
from services.score_service import ScoreService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])
CUSTOMER_STATUS_PATTERN = "^(" + "|".join(re.escape(status.value) for status in CustomerStatus) + ")$"
STATUS_CHANGE_PATTERN = "^(active|inactive|blocked)$"


def _enrichment_status_value(next_refresh_at, now=None) -> str:
    """Derive 'stale' | 'enriched' from a next_refresh_at timestamp.

    Falls back to 'enriched' when next_refresh_at is None (not yet computed).
    """
    if now is None:
        now = datetime.now(UTC)
    if next_refresh_at is not None and next_refresh_at <= now:
        return "stale"
    return "enriched"


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


async def _enrichment_status(
    customer_ids: list[int],
    session: AsyncSession,
    tenant_id: int,
) -> dict[int, dict]:
    """Batch-fetch the most recent enrichment record per customer and return status map.

    Returns a dict mapping customer_id -> {"enrichment_status": str, "last_enriched_at": str|None}.
    Uses a subquery to find max(enriched_at) per customer before fetching full rows.
    """
    if not customer_ids:
        return {}

    now = datetime.now(UTC)
    latest_subq = (
        select(
            CustomerEnrichmentModel.customer_id,
            func.max(CustomerEnrichmentModel.enriched_at).label("max_enriched_at"),
        )
        .where(
            and_(
                CustomerEnrichmentModel.customer_id.in_(customer_ids),
                CustomerEnrichmentModel.tenant_id == tenant_id,
            )
        )
        .group_by(CustomerEnrichmentModel.customer_id)
        .subquery()
    )
    result = await session.execute(
        select(CustomerEnrichmentModel)
        .where(
            and_(
                CustomerEnrichmentModel.customer_id.in_(customer_ids),
                CustomerEnrichmentModel.tenant_id == tenant_id,
                tuple_(
                    CustomerEnrichmentModel.customer_id,
                    CustomerEnrichmentModel.enriched_at,
                ).in_(select(latest_subq.c.customer_id, latest_subq.c.max_enriched_at)),
            )
        )
        .order_by(CustomerEnrichmentModel.enriched_at.desc(), CustomerEnrichmentModel.id.desc())
    )
    status_map: dict[int, dict] = {}
    for enrichment in result.scalars().all():
        last_enriched = enrichment.enriched_at.isoformat() if enrichment.enriched_at else None
        status = _enrichment_status_value(enrichment.next_refresh_at, now=now)
        status_map[enrichment.customer_id] = {"enrichment_status": status, "last_enriched_at": last_enriched}

    # Mark customers with no enrichment record
    for cid in customer_ids:
        if cid not in status_map:
            status_map[cid] = {"enrichment_status": "none", "last_enriched_at": None}

    return status_map


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
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    routing_svc = LeadRoutingService(repo.session)
    result = await service.create_customer(body.model_dump(), tenant_id=ctx.tenant_id, routing_service=routing_svc)
    return {"success": True, "data": result.to_dict(), "message": "客户创建成功"}


@customers_router.get("")
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    owner_id: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    items, total = await service.list_customers(
        page=page,
        page_size=page_size,
        status=status,
        owner_id=owner_id,
        tenant_id=ctx.tenant_id,
    )
    customer_ids = [getattr(c, "id", None) for c in items]
    customer_ids = [cid for cid in customer_ids if cid is not None]
    enrichment_status_map = await _enrichment_status(customer_ids, session, ctx.tenant_id)

    enriched_items = []
    for customer in items:
        d = customer.to_dict() if hasattr(customer, "to_dict") else customer
        cust_id = getattr(customer, "id", None)
        status_info = enrichment_status_map.get(cust_id, {"enrichment_status": "none", "last_enriched_at": None})
        d["enrichment_status"] = status_info["enrichment_status"]
        d["last_enriched_at"] = status_info["last_enriched_at"]
        enriched_items.append(d)

    return _paginated(enriched_items, total, page, page_size)


@customers_router.get("/search")
async def search_customers(
    keyword: str = Query("", max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    items = await service.search_customers(_sanitize(keyword), tenant_id=ctx.tenant_id)
    customer_ids = [getattr(c, "id", None) for c in items]
    customer_ids = [cid for cid in customer_ids if cid is not None]
    enrichment_status_map = await _enrichment_status(customer_ids, session, ctx.tenant_id)

    enriched_items = []
    for customer in items:
        d = customer.to_dict() if hasattr(customer, "to_dict") else customer
        cust_id = getattr(customer, "id", None)
        status_info = enrichment_status_map.get(cust_id, {"enrichment_status": "none", "last_enriched_at": None})
        d["enrichment_status"] = status_info["enrichment_status"]
        d["last_enriched_at"] = status_info["last_enriched_at"]
        enriched_items.append(d)

    return {"success": True, "data": {"keyword": keyword, "items": enriched_items}}


@customers_router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    data = result.to_dict() if hasattr(result, "to_dict") else result

    now = datetime.now(UTC)

    # Add derived enrichment status from joined enrichment record
    enrich_result = await session.execute(
        select(CustomerEnrichmentModel)
        .where(
            and_(
                CustomerEnrichmentModel.customer_id == customer_id,
                CustomerEnrichmentModel.tenant_id == ctx.tenant_id,
            )
        )
        .order_by(CustomerEnrichmentModel.enriched_at.desc(), CustomerEnrichmentModel.id.desc())
        .limit(1)
    )
    enrichment = enrich_result.scalar_one_or_none()
    if enrichment is None:
        data["enrichment_status"] = "none"
        data["last_enriched_at"] = None
    else:
        data["last_enriched_at"] = enrichment.enriched_at.isoformat() if enrichment.enriched_at else None
        data["enrichment_status"] = _enrichment_status_value(enrichment.next_refresh_at, now=now)

    return {"success": True, "data": data}


@customers_router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: dict,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.update_customer(customer_id, body, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "客户更新成功"}


@customers_router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.delete_customer(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "客户删除成功"}


@customers_router.post("/{customer_id}/tags")
async def add_tag(
    customer_id: int,
    body: TagOp,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.add_tag(customer_id, _sanitize(body.tag), tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "标签添加成功"}


@customers_router.delete("/{customer_id}/tags/{tag}")
async def remove_tag(
    customer_id: int,
    tag: str,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.remove_tag(customer_id, _sanitize(tag), tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "标签移除成功"}


@customers_router.put("/{customer_id}/status")
async def change_status(
    customer_id: int,
    body: StatusChange,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.change_status(customer_id, body.status, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "状态更新成功"}


@customers_router.put("/{customer_id}/owner")
async def assign_owner(
    customer_id: int,
    body: OwnerChange,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "负责人更新成功"}


@customers_router.post("/import")
async def bulk_import(
    body: BulkImport,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    repo = CustomerRepository(session)
    service = CustomerService(repo)
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
    session: AsyncSession = Depends(get_db),
):
    """Unassigned leads queue for the sales team."""
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    routing_svc = LeadRoutingService(repo.session)

    if status == "unassigned":
        items, total = await service.get_unassigned_leads(ctx.tenant_id, page=page, page_size=page_size)
    elif status == "assigned":
        items, total = await service.get_leads_by_owner(ctx.tenant_id, ctx.user_id, page=page, page_size=page_size)
    else:  # recycled
        conditions = and_(
            CustomerModel.tenant_id == ctx.tenant_id,
            CustomerModel.status == "lead",
            CustomerModel.recycle_count > 0,
        )
        count_result = await session.execute(select(func.count(CustomerModel.id)).where(conditions))
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
    session: AsyncSession = Depends(get_db),
):
    """Current assignment info for a customer."""
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    routing_svc = LeadRoutingService(repo.session)
    customer = await service.get_customer(customer_id, tenant_id=ctx.tenant_id)
    sla = routing_svc.get_sla_status(customer.assigned_at)

    # Fetch assigned user name if owner_id != 0
    assigned_to_name = None
    if customer.owner_id is not None and customer.owner_id > 0:
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
    session: AsyncSession = Depends(get_db),
):
    """Manually assign a customer to an owner, bypassing routing rules."""
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    result = await service.assign_owner(customer_id, body.owner_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict(), "message": "负责人分配成功"}


@customers_router.post("/{customer_id}/reassign")
async def reassign_lead(
    customer_id: int,
    body: ReassignLead,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Reassign a lead with reason logged to recycle_history."""
    repo = CustomerRepository(session)
    service = CustomerService(repo)
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
    session: AsyncSession = Depends(get_db),
):
    """Manually trigger lead recycle (admin/manager only)."""
    if "admin" not in ctx.roles and "manager" not in ctx.roles:
        raise ForbiddenException("需要 admin 或 manager 角色")
    repo = CustomerRepository(session)
    service = CustomerService(repo)
    recycled = await service.bulk_recycle(body.customer_ids, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {"recycled_ids": recycled},
        "message": f"已回收 {len(recycled)} 个线索",
    }


# ---------------------------------------------------------------------------
# Customer scoring endpoints (analytics)
# ---------------------------------------------------------------------------


@customers_router.post("/{customer_id}/score")
async def calculate_customer_score(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Trigger score calculation for a customer."""
    service = ScoreService(session)
    result = await service.calculate_score(customer_id, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {
            "score": result[0],
            "tier": result[1],
            "top_factors": result[2],
            "recommendations": result[3],
        },
    }


@customers_router.get("/{customer_id}/score")
async def get_customer_score(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get the current score for a customer. Returns 404 if the customer has never been scored."""
    service = ScoreService(session)
    result = await service.get_score(customer_id, tenant_id=ctx.tenant_id)
    if not result[2] and not result[3]:
        raise NotFoundException("Score")
    return {
        "success": True,
        "data": {
            "score": result[0],
            "tier": result[1],
            "top_factors": result[2],
            "recommendations": result[3],
        },
    }
