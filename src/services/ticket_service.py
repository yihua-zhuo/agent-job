from datetime import datetime, timedelta
from typing import Optional, List, Dict

from src.models.ticket import (
    Ticket,
    TicketReply,
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
    SLA_CONFIGS,
)
from src.models.response import ApiResponse, PaginatedData, ApiError


class TicketService:
    def __init__(self):
        self._tickets = {}
        self._replies = {}
        self._next_id = 1
        self._agent_pool = [1, 2, 3]  # 示例客服ID池
        self._agent_index = 0

    def _owned_by(self, ticket: Optional[Ticket], tenant_id: int) -> bool:
        """Return True if the ticket exists and belongs to the tenant (or tenant check skipped)."""
        if ticket is None:
            return False
        if not tenant_id:
            return True
        return ticket.tenant_id == tenant_id

    def create_ticket(
        self,
        subject: str,
        description: str,
        customer_id: int,
        channel: TicketChannel,
        priority: TicketPriority = TicketPriority.MEDIUM,
        sla_level: SLALevel = SLALevel.STANDARD,
        assigned_to: Optional[int] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[Ticket]:
        """创建工单"""
        now = datetime.utcnow()
        sla_config = SLA_CONFIGS[sla_level]
        response_deadline = now + timedelta(hours=sla_config.first_response_hours)


        ticket = Ticket(
            id=self._next_id,
            tenant_id=tenant_id,
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

        if assigned_to is None and ticket.id is not None:
            self.auto_assign(ticket.id, tenant_id=tenant_id)


        return ApiResponse.success(data=ticket, message='工单创建成功')

    def get_ticket(self, ticket_id: int, tenant_id: int = 0) -> ApiResponse[Ticket]:
        """获取工单"""
        ticket = self._tickets.get(ticket_id)
        if not self._owned_by(ticket, tenant_id):
            return ApiResponse.error(message='工单不存在', code=1404)
        return ApiResponse.success(data=ticket)

    def update_ticket(self, ticket_id: int, tenant_id: int = 0, **kwargs) -> ApiResponse[Ticket]:
        """更新工单"""
        ticket = self._tickets.get(ticket_id)
        if not self._owned_by(ticket, tenant_id):
            return ApiResponse.error(message='工单不存在', code=1404)

        # tenant_id should never be mutated via update
        kwargs.pop('tenant_id', None)
        for key, value in kwargs.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.updated_at = datetime.utcnow()
        return ApiResponse.success(data=ticket, message='工单更新成功')

    def assign_ticket(self, ticket_id: int, assigned_to: int, tenant_id: int = 0) -> ApiResponse[Ticket]:
        """分配客服"""
        result = self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=assigned_to)
        if result:
            result.message = '客服分配成功'
        return result

    def add_reply(
        self, ticket_id: int, content: str, created_by: int, is_internal: bool = False, tenant_id: int = 0
    ) -> ApiResponse[TicketReply]:
        """添加回复"""
        ticket = self._tickets.get(ticket_id)
        if not self._owned_by(ticket, tenant_id):
            return ApiResponse.error(message='工单不存在', code=1404)

        reply = TicketReply(
            id=len(self._replies[ticket_id]) + 1,
            tenant_id=ticket.tenant_id,
            ticket_id=ticket_id,
            content=content,
            is_internal=is_internal,
            created_by=created_by,
            created_at=datetime.utcnow(),
        )

        self._replies[ticket_id].append(reply)

        # 更新 first_response_at（首次回复时间）
        if not ticket.first_response_at and not is_internal:
            ticket.first_response_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()

        return ApiResponse.success(data=reply, message='回复添加成功')

    def change_status(self, ticket_id: int, new_status: TicketStatus, tenant_id: int = 0) -> ApiResponse[Ticket]:
        """改变状态"""
        ticket = self._tickets.get(ticket_id)
        if not self._owned_by(ticket, tenant_id):
            return ApiResponse.error(message='工单不存在', code=1404)

        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()


        # RESOLVED 时记录 resolved_at
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()

        return ApiResponse.success(data=ticket, message=f'工单状态已更新为{new_status}')

    def get_customer_tickets(self, customer_id: int, tenant_id: int = 0) -> List[Ticket]:
        """获取客户的所有工单"""
        return [
            t for t in self._tickets.values()
            if t.customer_id == customer_id and self._owned_by(t, tenant_id)
        ]

    def list_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[int] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[PaginatedData[Ticket]]:
        """工单列表"""
        tickets = [t for t in self._tickets.values() if self._owned_by(t, tenant_id)]

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
        items = tickets[start:end]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message='查询成功'
        )

    def get_sla_breaches(self, tenant_id: int = 0) -> List[Ticket]:
        """获取SLA超时的工单"""
        return [
            t for t in self._tickets.values()
            if self._owned_by(t, tenant_id) and t.check_sla_breach()
        ]

    def auto_assign(self, ticket_id: int, tenant_id: int = 0) -> ApiResponse[Dict]:
        """自动分配客服"""
        ticket = self._tickets.get(ticket_id)
        if not self._owned_by(ticket, tenant_id):
            return ApiResponse.error(message='工单不存在', code=1404)
        if ticket.assigned_to is not None:
            return ApiResponse.success(data={'agent_id': ticket.assigned_to}, message='工单已分配客服')


        agent_id = self._agent_pool[self._agent_index % len(self._agent_pool)]
        self._agent_index += 1
        ticket.assigned_to = agent_id
        ticket.updated_at = datetime.utcnow()
        return ApiResponse.success(data={'agent_id': agent_id}, message='自动分配客服成功')
