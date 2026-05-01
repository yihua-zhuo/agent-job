"""SLA management service - async PostgreSQL via SQLAlchemy."""
from datetime import datetime, timedelta, UTC
from typing import List, Literal, Optional

from sqlalchemy import text

from db.connection import get_db_session
from models.ticket import Ticket, SLALevel, SLA_CONFIGS


class SLAService:
    """SLA管理"""

    def __init__(self, ticket_service=None):
        self._ticket_service = ticket_service

    async def check_sla_status(
        self, ticket: Ticket
    ) -> Literal["normal", "warning", "breached"]:
        """检查SLA状态"""
        # 返回：正常、临近超时、已超时
        if ticket.resolved_at:
            return "normal"

        if ticket.check_sla_breach():
            return "breached"

        # 临近超时：剩余时间少于 SLA 时间的 25%
        if not ticket.response_deadline:
            return "normal"

        sla_config = SLA_CONFIGS.get(ticket.sla_level)
        if not sla_config:
            return "normal"

        total_hours = sla_config.first_response_hours
        remaining = await self.calculate_remaining_time(ticket)
        warning_threshold = total_hours * 0.25

        if remaining.total_seconds() < warning_threshold * 3600:
            return "warning"

        return "normal"

    async def get_breach_tickets(
        self, tenant_id: int, tickets: List[Ticket] = None
    ) -> List[Ticket]:
        """获取所有超时的工单（按租户隔离）"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, subject, description, status, priority, channel,
                           customer_id, sla_level, tenant_id, assigned_to,
                           created_at, updated_at, resolved_at,
                           first_response_at, response_deadline
                    FROM tickets
                    WHERE tenant_id = :tenant_id
                      AND response_deadline < :now
                      AND resolved_at IS NULL
                    """
                ),
                {"tenant_id": tenant_id, "now": now},
            )
            rows = result.fetchall()
            return [self._row_to_ticket(r) for r in rows]

    async def calculate_remaining_time(self, ticket: Ticket) -> timedelta:
        """计算剩余时间"""
        if not ticket.response_deadline:
            return timedelta(0)

        if ticket.resolved_at:
            return timedelta(0)

        remaining = ticket.response_deadline - datetime.now(UTC)
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def _row_to_ticket(self, row) -> Ticket:
        """Map a tickets DB row to a Ticket dataclass instance."""
        # Columns: id, subject, description, status, priority, channel,
        #          customer_id, sla_level, tenant_id, assigned_to,
        #          created_at, updated_at, resolved_at, first_response_at, response_deadline
        from models.ticket import (
            TicketStatus, TicketPriority, TicketChannel,
        )

        def _enum(cls, val):
            try:
                return next(e for e in cls if e.value == val)
            except StopIteration:
                return None

        return Ticket(
            id=row[0],
            subject=row[1],
            description=row[2],
            status=_enum(TicketStatus, row[3]) or TicketStatus.OPEN,
            priority=_enum(TicketPriority, row[4]) or TicketPriority.MEDIUM,
            channel=_enum(TicketChannel, row[5]) or TicketChannel.EMAIL,
            customer_id=row[6],
            sla_level=_enum(SLALevel, row[7]) or SLALevel.STANDARD,
            tenant_id=row[8],
            assigned_to=row[9],
            created_at=row[10],
            updated_at=row[11],
            resolved_at=row[12],
            first_response_at=row[13],
            response_deadline=row[14],
        )
