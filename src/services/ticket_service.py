from datetime import datetime, timedelta
from typing import Optional, List

from src.models.ticket import (
    Ticket,
    TicketReply,
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
    SLA_CONFIGS,
)


class TicketService:
    def __init__(self):
        self._tickets = {}
        self._replies = {}
        self._next_id = 1
        self._agent_pool = [1, 2, 3]  # 示例客服ID池
        self._agent_index = 0

    def create_ticket(
        self,
        subject: str,
        description: str,
        customer_id: int,
        channel: TicketChannel,
        priority: TicketPriority = TicketPriority.MEDIUM,
        sla_level: SLALevel = SLALevel.STANDARD,
        assigned_to: Optional[int] = None,
    ) -> Ticket:
        """创建工单"""
        now = datetime.now()
        sla_config = SLA_CONFIGS[sla_level]
        response_deadline = now + timedelta(hours=sla_config.first_response_hours)

        ticket = Ticket(
            id=self._next_id,
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

        self._tickets[self._next_id] = ticket
        self._replies[self._next_id] = []
        self._next_id += 1

        if assigned_to is None:
            self.auto_assign(ticket.id)

        return ticket

    def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """获取工单"""
        return self._tickets.get(ticket_id)

    def update_ticket(self, ticket_id: int, **kwargs) -> Optional[Ticket]:
        """更新工单"""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        for key, value in kwargs.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.updated_at = datetime.now()
        return ticket

    def assign_ticket(self, ticket_id: int, assigned_to: int) -> Optional[Ticket]:
        """分配客服"""
        return self.update_ticket(ticket_id, assigned_to=assigned_to)

    def add_reply(
        self, ticket_id: int, content: str, created_by: int, is_internal: bool = False
    ) -> Optional[TicketReply]:
        """添加回复"""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        reply = TicketReply(
            id=len(self._replies[ticket_id]) + 1,
            ticket_id=ticket_id,
            content=content,
            is_internal=is_internal,
            created_by=created_by,
            created_at=datetime.now(),
        )

        self._replies[ticket_id].append(reply)

        # 更新 first_response_at（首次回复时间）
        if not ticket.first_response_at and not is_internal:
            ticket.first_response_at = datetime.now()
            ticket.updated_at = datetime.now()

        return reply

    def change_status(self, ticket_id: int, new_status: TicketStatus) -> Optional[Ticket]:
        """改变状态"""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.status = new_status
        ticket.updated_at = datetime.now()

        # RESOLVED 时记录 resolved_at
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.now()

        return ticket

    def get_customer_tickets(self, customer_id: int) -> List[Ticket]:
        """获取客户的所有工单"""
        return [t for t in self._tickets.values() if t.customer_id == customer_id]

    def list_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[int] = None,
    ) -> List[Ticket]:
        """工单列表"""
        tickets = list(self._tickets.values())

        if status:
            tickets = [t for t in tickets if t.status == status]
        if priority:
            tickets = [t for t in tickets if t.priority == priority]
        if assigned_to is not None:
            tickets = [t for t in tickets if t.assigned_to == assigned_to]

        tickets.sort(key=lambda t: t.created_at, reverse=True)

        start = (page - 1) * page_size
        end = start + page_size
        return tickets[start:end]

    def get_sla_breaches(self) -> List[Ticket]:
        """获取SLA超时的工单"""
        return [t for t in self._tickets.values() if t.check_sla_breach()]

    def auto_assign(self, ticket_id: int) -> Optional[int]:
        """自动分配客服"""
        ticket = self._tickets.get(ticket_id)
        if not ticket or ticket.assigned_to is not None:
            return ticket.assigned_to if ticket else None

        agent_id = self._agent_pool[self._agent_index % len(self._agent_pool)]
        self._agent_index += 1
        ticket.assigned_to = agent_id
        ticket.updated_at = datetime.now()
        return agent_id
