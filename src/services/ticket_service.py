from datetime import datetime, timedelta

from models.response import ResponseStatus
from models.ticket import (
    SLA_CONFIGS,
    SLALevel,
    Ticket,
    TicketChannel,
    TicketPriority,
    TicketReply,
    TicketStatus,
)

# Module-level state so tickets persist across service instances per test
_tickets_db: dict = {}
_ticket_replies_db: dict = {}
_ticket_next_id = 1
_ticket_agent_pool = [1, 2, 3]
_ticket_agent_index = 0


class TicketService:
    def __init__(self, session):
        self._session = session

    async def create_ticket(
        self,
        subject: str,
        description: str,
        customer_id: int,
        channel: TicketChannel,
        priority: TicketPriority = TicketPriority.MEDIUM,
        sla_level: SLALevel = SLALevel.STANDARD,
        assigned_to: int | None = None,
        tenant_id: int = 0,
    ) -> dict:
        """创建工单"""
        now = datetime.now()
        sla_config = SLA_CONFIGS[sla_level]
        response_deadline = now + timedelta(hours=sla_config.first_response_hours)

        global _ticket_next_id, _ticket_agent_index
        ticket = Ticket(
            id=_ticket_next_id,
            subject=subject,
            description=description,
            status=TicketStatus.OPEN,
            priority=priority,
            channel=channel,
            customer_id=customer_id,
            assigned_to=assigned_to,
            sla_level=sla_level,
            created_at=now,
            updated_at=now,
            resolved_at=None,
            first_response_at=None,
            response_deadline=response_deadline,
        )

        _tickets_db[_ticket_next_id] = ticket
        _ticket_replies_db[_ticket_next_id] = []
        _ticket_next_id += 1

        if assigned_to is None:
            _auto_assign(ticket.id)

        return {"status": ResponseStatus.SUCCESS, "data": ticket, "message": "工单创建成功"}

    async def get_ticket(self, ticket_id: int, tenant_id: int = 0) -> dict:
        ticket = _tickets_db.get(ticket_id)
        if not ticket:
            return {"status": ResponseStatus.NOT_FOUND, "data": None, "message": "Ticket not found"}
        return {"status": ResponseStatus.SUCCESS, "data": ticket, "message": ""}

    async def update_ticket(self, ticket_id: int, tenant_id: int = 0, **kwargs) -> dict:
        ticket = _tickets_db.get(ticket_id)
        if not ticket:
            return {"status": ResponseStatus.NOT_FOUND, "data": None, "message": "Ticket not found"}
        for key, value in kwargs.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.updated_at = datetime.now()
        return {"status": ResponseStatus.SUCCESS, "data": ticket, "message": "工单更新成功"}

    async def assign_ticket(self, ticket_id: int, assigned_to: int, tenant_id: int = 0) -> dict:
        return await self.update_ticket(ticket_id, assigned_to=assigned_to)

    async def add_reply(self, ticket_id: int, content: str, created_by: int, is_internal: bool = False, tenant_id: int = 0) -> dict:
        ticket = _tickets_db.get(ticket_id)
        if not ticket:
            return {"status": ResponseStatus.NOT_FOUND, "data": None, "message": "Ticket not found"}
        reply = TicketReply(
            id=len(_ticket_replies_db[ticket_id]) + 1,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            content=content,
            is_internal=is_internal,
            created_by=created_by,
            created_at=datetime.now(),
        )
        _ticket_replies_db[ticket_id].append(reply)
        if not ticket.first_response_at and not is_internal:
            ticket.first_response_at = datetime.now()
            ticket.updated_at = datetime.now()
        return {"status": ResponseStatus.SUCCESS, "data": reply, "message": ""}

    async def change_status(self, ticket_id: int, new_status: TicketStatus, tenant_id: int = 0) -> dict:
        ticket = _tickets_db.get(ticket_id)
        if not ticket:
            return {"status": ResponseStatus.NOT_FOUND, "data": None, "message": "Ticket not found"}
        ticket.status = new_status
        ticket.updated_at = datetime.now()
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.now()
        return {"status": ResponseStatus.SUCCESS, "data": ticket, "message": "状态更新成功"}

    async def get_customer_tickets(self, customer_id: int, tenant_id: int = 0) -> dict:
        tickets = [t for t in _tickets_db.values() if t.customer_id == customer_id]
        return {"status": ResponseStatus.SUCCESS, "data": tickets, "message": ""}

    async def list_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        assigned_to: int | None = None,
        tenant_id: int = 0,
    ) -> dict:
        """工单列表"""
        tickets = list(_tickets_db.values())

        if status:
            tickets = [t for t in tickets if t.status == status]
        if priority:
            tickets = [t for t in tickets if t.priority == priority]
        if assigned_to is not None:
            tickets = [t for t in tickets if t.assigned_to == assigned_to]

        tickets.sort(key=lambda t: t.created_at, reverse=True)

        total = len(tickets)
        start = (page - 1) * page_size
        end = start + page_size
        page_tickets = tickets[start:end]
        pg = {
            "items": page_tickets,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "has_next": end < total,
            "has_prev": page > 1,
        }
        return {
            "status": ResponseStatus.SUCCESS,
            "data": pg,
            "message": "",
        }

    async def get_sla_breaches(self, tenant_id: int = 0) -> dict:
        """获取SLA超时的工单"""
        tickets = [t for t in _tickets_db.values() if t.check_sla_breach()]
        return {"status": ResponseStatus.SUCCESS, "data": tickets, "message": ""}

    async def auto_assign(self, ticket_id: int, tenant_id: int = 0) -> dict:
        """自动分配客服"""
        result = _auto_assign(ticket_id)
        return {"status": ResponseStatus.SUCCESS, "data": {"ticket_id": ticket_id, "assigned_to": result}, "message": ""}


def _auto_assign(ticket_id: int) -> int | None:
    global _ticket_agent_index
    ticket = _tickets_db.get(ticket_id)
    if not ticket or ticket.assigned_to is not None:
        return ticket.assigned_to if ticket else None

    agent_id = _ticket_agent_pool[_ticket_agent_index % len(_ticket_agent_pool)]
    _ticket_agent_index += 1
    ticket.assigned_to = agent_id
    ticket.updated_at = datetime.now()
    return agent_id
