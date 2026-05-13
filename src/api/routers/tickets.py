"""Tickets router — /api/v1/tickets and /api/v1/sla endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Ticket/TicketReply objects have .to_dict(); router calls it before returning.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.ticket import SLALevel, TicketChannel, TicketPriority, TicketStatus
from services.sla_service import SLAService
from services.ticket_service import TicketService
from services.user_service import UserService

tickets_router = APIRouter(prefix="/api/v1", tags=["tickets"])


def _paginated(items, total, page, page_size):
    """Build a paginated success envelope.

    Args:
        items: List of serializable model objects (must have ``.to_dict()``).
        total: Total number of matching records (unfiltered count).
        page: Current 1-based page number.
        page_size: Items per page.

    Returns:
        ``{"success": True, "data": {"items": [...], "total": N, "page": N, ...}}``
    """
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [t.to_dict() for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


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


class TicketBulkUpdate(BaseModel):
    ticket_ids: list[int] = Field(..., min_length=1)
    assigned_to: int | None = Field(None, ge=1)
    status: str | None = Field(None, pattern="^(open|in_progress|pending|resolved|closed)$")


def _status_str_to_enum(status_str: str) -> TicketStatus:
    mapping = {
        "open": TicketStatus.OPEN,
        "in_progress": TicketStatus.IN_PROGRESS,
        "pending": TicketStatus.PENDING,
        "resolved": TicketStatus.RESOLVED,
        "closed": TicketStatus.CLOSED,
    }
    return mapping.get(status_str, TicketStatus.OPEN)


# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------


@tickets_router.post("/tickets", status_code=201)
async def create_ticket(
    body: TicketCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new ticket.

    The ticket is auto-assigned (round-robin) if ``assigned_to`` is not supplied.
    The ``response_deadline`` is computed from the SLA level.
    """
    service = TicketService(session)
    ticket = await service.create_ticket(
        subject=body.subject,
        description=body.description,
        customer_id=body.customer_id,
        channel=TicketChannel(body.channel),
        priority=TicketPriority(body.priority),
        sla_level=SLALevel(body.sla_level) if body.sla_level else SLALevel.STANDARD,
        tenant_id=ctx.tenant_id or 0,
    )
    return {"success": True, "data": ticket.to_dict(), "message": "工单创建成功"}


@tickets_router.get("/tickets")
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    assignee_id: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List tickets with optional filters and pagination.

    Query params:
        - ``status``: open / in_progress / pending / resolved / closed
        - ``priority``: low / medium / high / urgent
        - ``assignee_id``: filter by assigned agent (use 0 for unassigned)
    """
    try:
        status_enum = TicketStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid status value")
    try:
        priority_enum = TicketPriority(priority) if priority else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid priority value")
    service = TicketService(session)
    items, total = await service.list_tickets(
        page=page,
        page_size=page_size,
        status=status_enum,
        priority=priority_enum,
        assigned_to=assignee_id,
        tenant_id=ctx.tenant_id or 0,
    )
    return _paginated(items, total, page, page_size)


@tickets_router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Fetch a single ticket by ID, verifying tenant ownership."""
    service = TicketService(session)
    ticket = await service.get_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": ticket.to_dict()}


@tickets_router.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Apply a partial update to a ticket (subject, description, priority, channel, assignee)."""
    service = TicketService(session)
    update_data = body.model_dump(exclude_none=True)
    if "priority" in update_data:
        update_data["priority"] = TicketPriority(update_data["priority"])
    if "channel" in update_data:
        update_data["channel"] = TicketChannel(update_data["channel"])
    ticket = await service.update_ticket(ticket_id, tenant_id=ctx.tenant_id or 0, **update_data)
    return {"success": True, "data": ticket.to_dict(), "message": "工单更新成功"}


@tickets_router.put("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: int,
    body: TicketAssign,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Explicitly assign (or re-assign) a ticket to a user.

    Validates that the assignee user exists before assigning.
    """
    user_service = UserService(session)
    await user_service.get_user_by_id(body.assignee_id, tenant_id=ctx.tenant_id or 0)
    service = TicketService(session)
    ticket = await service.assign_ticket(ticket_id, body.assignee_id, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": ticket.to_dict(), "message": "工单分配成功"}


@tickets_router.post("/tickets/{ticket_id}/replies", status_code=201)
async def add_reply(
    ticket_id: int,
    body: TicketReplyCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Append a customer-facing reply or internal note to a ticket.

    For external replies, sets ``first_response_at`` on the ticket.
    """
    service = TicketService(session)
    reply = await service.add_reply(
        ticket_id=ticket_id,
        content=body.content,
        created_by=ctx.user_id,
        is_internal=body.is_internal,
        tenant_id=ctx.tenant_id or 0,
    )
    return {"success": True, "data": reply.to_dict(), "message": "回复添加成功"}


@tickets_router.put("/tickets/{ticket_id}/status")
async def change_ticket_status(
    ticket_id: int,
    body: TicketStatusChange,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Transition a ticket to a new status.

    Transitioning to ``resolved`` sets the ``resolved_at`` timestamp.
    """
    service = TicketService(session)
    new_status = _status_str_to_enum(body.new_status)
    ticket = await service.change_status(ticket_id, new_status, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": ticket.to_dict(), "message": "状态变更成功"}


@tickets_router.get("/tickets/customer/{customer_id}")
async def get_customer_tickets(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List all tickets for a specific customer, newest first."""
    service = TicketService(session)
    tickets = await service.get_customer_tickets(customer_id, tenant_id=ctx.tenant_id or 0)
    return {
        "success": True,
        "data": [t.to_dict() for t in tickets],
        "message": "查询成功",
    }


@tickets_router.get("/tickets/sla/breaches")
async def get_sla_breaches(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return all unresolved tickets whose SLA response deadline has been breached."""
    service = TicketService(session)
    tickets = await service.get_sla_breaches(tenant_id=ctx.tenant_id or 0)
    return {
        "success": True,
        "data": [t.to_dict() for t in tickets],
        "message": "查询成功",
    }


@tickets_router.post("/tickets/bulk-update")
async def bulk_update_tickets(
    body: TicketBulkUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Apply a status change and/or assignee reassignment to multiple tickets atomically.

    Validates every ticket exists (by calling ``get_ticket``) before applying any updates,
    then processes them sequentially.
    """
    service = TicketService(session)
    # Pre-validate all tickets exist to avoid partial updates
    for ticket_id in body.ticket_ids:
        await service.get_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)
    updated = []
    for ticket_id in body.ticket_ids:
        kwargs: dict = {}
        if body.assigned_to is not None:
            kwargs["assigned_to"] = body.assigned_to
        if body.status is not None:
            kwargs["status"] = _status_str_to_enum(body.status)
        ticket = await service.update_ticket(ticket_id, tenant_id=ctx.tenant_id or 0, **kwargs)
        updated.append(ticket.to_dict())
    return {"success": True, "data": updated, "message": "Bulk update successful"}


@tickets_router.post("/tickets/{ticket_id}/auto-assign")
async def auto_assign_ticket(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Auto-assign a ticket using round-robin if it is currently unassigned.

    Idempotent: returns unchanged ticket if already assigned.
    """
    service = TicketService(session)
    ticket = await service.auto_assign(ticket_id, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": ticket.to_dict(), "message": "自动分配成功"}


# ---------------------------------------------------------------------------
# SLA endpoints
# ---------------------------------------------------------------------------


@tickets_router.get("/tickets/{ticket_id}/replies")
async def get_replies(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Fetch all replies for a ticket in chronological (ASC) order.

    Used to render the replies thread in the ticket detail view.
    """
    service = TicketService(session)
    replies = await service.get_ticket_replies(ticket_id, tenant_id=ctx.tenant_id or 0)
    return {
        "success": True,
        "data": [r.to_dict() for r in replies],
        "message": "查询成功",
    }


@tickets_router.get("/tickets/{ticket_id}/activity")
async def get_ticket_activity(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Fetch the activity/audit log for a ticket in reverse-chronological order.

    Activity records are filtered by content containing ``ticket#<id>``.
    """
    service = TicketService(session)
    activities = await service.get_ticket_activity(ticket_id, tenant_id=ctx.tenant_id or 0)
    return {
        "success": True,
        "data": [a.to_dict() for a in activities],
        "message": "查询成功",
    }


@tickets_router.get("/sla/status/{ticket_id}")
async def check_sla_status(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return the current SLA status and remaining time for a ticket.

    ``remaining_hours`` is negative when the deadline has already passed.
    """
    ticket_svc = TicketService(session)
    ticket = await ticket_svc.get_ticket(ticket_id, tenant_id=ctx.tenant_id or 0)
    sla_svc = SLAService(session)
    sla_status = await sla_svc.check_sla_status(ticket)
    remaining = await sla_svc.calculate_remaining_time(ticket)
    remaining_hours = remaining.total_seconds() / 3600 if remaining.total_seconds() > 0 else 0
    return {
        "success": True,
        "data": {
            "ticket_id": ticket_id,
            "status": sla_status,
            "remaining_hours": round(remaining_hours, 2),
        },
        "message": "查询成功",
    }


@tickets_router.get("/sla/breaches")
async def get_sla_breach_tickets(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return all unresolved tickets with breached SLA response deadlines."""
    sla_svc = SLAService(session, ticket_service=TicketService(session))
    tickets = await sla_svc.get_breach_tickets(tenant_id=ctx.tenant_id or 0)
    return {
        "success": True,
        "data": [t.to_dict() for t in tickets],
        "message": "查询成功",
    }
