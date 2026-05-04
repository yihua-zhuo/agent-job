"""Tickets router — /api/v1/tickets and /api/v1/sla endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from models.ticket import SLALevel, TicketChannel, TicketPriority, TicketStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope
from services.sla_service import SLAService
from services.ticket_service import TicketService

tickets_router = APIRouter(prefix='/api/v1', tags=['tickets'])


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

class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., max_length=10000)
    customer_id: int = Field(..., ge=1)
    channel: str = Field(..., pattern="^(email|chat|whatsapp|phone)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    sla_level: str | None = Field(default="standard", pattern="^(basic|standard|premium|enterprise)$")


class TicketUpdate(BaseModel):
    subject: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=10000)
    priority: str | None = Field(None, pattern="^(low|medium|high|urgent)$")
    channel: str | None = Field(None, pattern="^(email|chat|whatsapp|phone)$")
    assigned_to: int | None = Field(None, ge=0)


class TicketAssign(BaseModel):
    assignee_id: int = Field(..., ge=1)


class TicketReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    created_by: int = Field(..., ge=1)
    is_internal: bool = Field(default=False)


class TicketStatusChange(BaseModel):
    new_status: str = Field(..., pattern="^(open|in_progress|pending|resolved|closed)$")


class TicketData(BaseModel):
    id: int
    tenant_id: int
    subject: str
    description: str
    status: str
    priority: str
    channel: str
    customer_id: int
    assigned_to: int | None = None
    sla_level: str
    created_at: str | None = None
    updated_at: str | None = None
    resolved_at: str | None = None
    first_response_at: str | None = None
    response_deadline: str | None = None


class TicketResponse(SuccessEnvelope):
    data: TicketData | None = None


class TicketListData(BaseModel):
    items: list[TicketData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class TicketListResponse(SuccessEnvelope):
    data: TicketListData


class ReplyData(BaseModel):
    id: int
    ticket_id: int
    tenant_id: int
    content: str
    is_internal: bool
    created_by: int
    created_at: str | None = None


class ReplyResponse(SuccessEnvelope):
    data: ReplyData


class AssignResponse(SuccessEnvelope):
    data: TicketData


class SLAStatusData(BaseModel):
    ticket_id: int
    status: str
    remaining_hours: float | None = None


class SLAStatusResponse(SuccessEnvelope):
    data: SLAStatusData


# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------

def _ticket_to_data(ticket) -> TicketData:
    # Handle both ORM objects and dict-like test mocks
    def _get(obj, *keys, default=None):
        for k in keys:
            if hasattr(obj, k):
                return getattr(obj, k)
            if isinstance(obj, dict) and k in obj:
                return obj[k]
        return default

    def _str(val, default=None):
        if val is None:
            return default
        return val.value if hasattr(val, "value") else str(val)

    def _dt(val):
        """Convert datetime to ISO string, or None."""
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return TicketData(
        id=_get(ticket, "id", "ticket_id", default=0) or 0,
        tenant_id=_get(ticket, "tenant_id", default=0) or 0,
        subject=_get(ticket, "subject", default="") or "",
        description=_get(ticket, "description", default="") or "",
        status=_str(_get(ticket, "status"), "open") or "open",
        priority=_str(_get(ticket, "priority"), "medium") or "medium",
        channel=_str(_get(ticket, "channel"), "email") or "email",
        customer_id=_get(ticket, "customer_id", default=0) or 0,
        assigned_to=_get(ticket, "assigned_to"),
        sla_level=_str(_get(ticket, "sla_level"), "standard") or "standard",
        created_at=_dt(_get(ticket, "created_at")),
        updated_at=_dt(_get(ticket, "updated_at")),
        resolved_at=_dt(_get(ticket, "resolved_at")),
        first_response_at=_dt(_get(ticket, "first_response_at")),
        response_deadline=_dt(_get(ticket, "response_deadline")),
    )


def _reply_to_data(reply) -> ReplyData:
    return ReplyData(
        id=reply.id,
        ticket_id=reply.ticket_id,
        tenant_id=reply.tenant_id,
        content=reply.content,
        is_internal=reply.is_internal,
        created_by=reply.created_by,
        created_at=reply.created_at.isoformat() if reply.created_at else None,
    )


def _status_str_to_enum(status_str: str) -> TicketStatus:
    mapping = {
        "open": TicketStatus.OPEN,
        "in_progress": TicketStatus.IN_PROGRESS,
        "pending": TicketStatus.PENDING,
        "resolved": TicketStatus.RESOLVED,
        "closed": TicketStatus.CLOSED,
    }
    return mapping.get(status_str, TicketStatus.OPEN)


@tickets_router.post(
    '/tickets',
    status_code=201,
    response_model=TicketResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_ticket(
    body: TicketCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.create_ticket(
        subject=body.subject,
        description=body.description,
        customer_id=body.customer_id,
        channel=TicketChannel(body.channel),
        priority=TicketPriority(body.priority),
        sla_level=SLALevel(body.sla_level) if body.sla_level else SLALevel.STANDARD,
        tenant_id=ctx.tenant_id or 0,
    )
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return TicketResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


@tickets_router.get(
    '/tickets',
    response_model=TicketListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    assignee_id: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    try:
        status_enum = TicketStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid status value")
    try:
        priority_enum = TicketPriority(priority) if priority else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid priority value")
    resp = await service.list_tickets(
        page=page, page_size=page_size,
        status=status_enum, priority=priority_enum,
        assigned_to=assignee_id, tenant_id=ctx.tenant_id or 0,
    )
    status_code = _http_status(resp["status"])
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp["message"])
    _pd = resp["data"]
    items = [_ticket_to_data(t) for t in _pd["items"]]
    total_pages = (_pd["total"] + _pd["page_size"] - 1) // _pd["page_size"] if _pd["page_size"] > 0 else 0
    return TicketListResponse(
        message=resp["message"],
        data=TicketListData(
            items=items,
            total=_pd["total"],
            page=_pd["page"],
            page_size=_pd["page_size"],
            total_pages=total_pages,
            has_next=_pd["page"] < total_pages,
            has_prev=_pd["page"] > 1,
        ),
    )


@tickets_router.get(
    '/tickets/{ticket_id}',
    response_model=TicketResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def get_ticket(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.get_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return TicketResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


@tickets_router.put(
    '/tickets/{ticket_id}',
    response_model=TicketResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    update_data = body.model_dump(exclude_none=True)
    # Coerce priority/channel enums if present
    if "priority" in update_data:
        update_data["priority"] = TicketPriority(update_data["priority"])
    if "channel" in update_data:
        update_data["channel"] = TicketChannel(update_data["channel"])
    resp = await service.update_ticket(ticket_id, tenant_id=ctx.tenant_id or 0, **update_data)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return TicketResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


@tickets_router.put(
    '/tickets/{ticket_id}/assign',
    response_model=AssignResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def assign_ticket(
    ticket_id: int,
    body: TicketAssign,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.assign_ticket(ticket_id, body.assignee_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return AssignResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


@tickets_router.post(
    '/tickets/{ticket_id}/replies',
    status_code=201,
    response_model=ReplyResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def add_reply(
    ticket_id: int,
    body: TicketReplyCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.add_reply(
        ticket_id=ticket_id,
        content=body.content,
        created_by=ctx.user_id,
        is_internal=body.is_internal,
        tenant_id=ctx.tenant_id or 0,
    )
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return ReplyResponse(message=resp["message"], data=_reply_to_data(resp["data"]))


@tickets_router.put(
    '/tickets/{ticket_id}/status',
    response_model=TicketResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def change_ticket_status(
    ticket_id: int,
    body: TicketStatusChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    new_status = _status_str_to_enum(body.new_status)
    resp = await service.change_status(ticket_id, new_status, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return TicketResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


@tickets_router.get(
    '/tickets/customer/{customer_id}',
    response_model=TicketListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_customer_tickets(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.get_customer_tickets(customer_id, tenant_id=ctx.tenant_id or 0)
    tickets = resp["data"] if isinstance(resp, dict) else resp
    items = [_ticket_to_data(t) for t in tickets]
    return TicketListResponse(
        message="查询成功",
        data=TicketListData(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
            has_next=False,
            has_prev=False,
        ),
    )


@tickets_router.get(
    '/tickets/sla/breaches',
    response_model=TicketListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_sla_breaches(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    tickets = await service.get_sla_breaches(tenant_id=ctx.tenant_id or 0)
    items = [_ticket_to_data(t) for t in tickets]
    return TicketListResponse(
        message="查询成功",
        data=TicketListData(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
            has_next=False,
            has_prev=False,
        ),
    )


@tickets_router.post(
    '/tickets/{ticket_id}/auto-assign',
    response_model=AssignResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def auto_assign_ticket(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = TicketService(session)
    resp = await service.auto_assign(ticket_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    return AssignResponse(message=resp["message"], data=_ticket_to_data(resp["data"]))


# ---------------------------------------------------------------------------
# SLA endpoints
# ---------------------------------------------------------------------------

@tickets_router.get(
    '/sla/status/{ticket_id}',
    response_model=SLAStatusResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def check_sla_status(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    ticket_svc = TicketService(session)
    resp = await ticket_svc.get_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp["status"])
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp["message"])
    ticket = resp["data"]
    sla_svc = SLAService(session)
    sla_status = await sla_svc.check_sla_status(ticket)
    remaining = await sla_svc.calculate_remaining_time(ticket)
    remaining_hours = remaining.total_seconds() / 3600 if remaining.total_seconds() > 0 else 0
    return SLAStatusResponse(
        message="查询成功",
        data=SLAStatusData(
            ticket_id=ticket_id,
            status=sla_status,
            remaining_hours=round(remaining_hours, 2),
        ),
    )


@tickets_router.get(
    '/sla/breaches',
    response_model=TicketListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_sla_breach_tickets(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    sla_svc = SLAService(session, ticket_service=TicketService(session))
    tickets = await sla_svc.get_breach_tickets(tenant_id=ctx.tenant_id or 0)
    items = [_ticket_to_data(t) for t in tickets]
    return TicketListResponse(
        message="查询成功",
        data=TicketListData(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
            has_next=False,
            has_prev=False,
        ),
    )
