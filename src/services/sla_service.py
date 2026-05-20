from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from models.ticket import SLA_CONFIGS, Ticket


class SLAService:
    """SLA管理"""

    def __init__(self, session: AsyncSession, ticket_service=None):
        self._session = session
        self._ticket_service = ticket_service

    def check_sla_status(self, ticket: Ticket) -> Literal["normal", "warning", "breached"]:
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
        remaining = self.calculate_remaining_time(ticket)
        warning_threshold = total_hours * 0.25

        if remaining.total_seconds() < warning_threshold * 3600:
            return "warning"

        return "normal"

    async def get_breach_tickets(self, tenant_id: int = 0, tickets: list[Ticket] = None) -> list[Ticket]:
        """Get all breached tickets, optionally from a provided list or via service query."""
        if tickets is None and self._ticket_service:
            tickets = await self._ticket_service.get_sla_breaches(tenant_id=tenant_id)
        return [t for t in (tickets or []) if t.check_sla_breach()]

    def calculate_remaining_time(self, ticket: Ticket) -> timedelta:
        """计算剩余时间"""
        if not ticket.response_deadline:
            return timedelta(0)

        if ticket.resolved_at:
            return timedelta(0)

        remaining = ticket.response_deadline - datetime.now(UTC)
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
