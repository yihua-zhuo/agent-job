from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ticket import TicketModel
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

    async def get_sla_summary(self, tenant_id: int) -> dict[str, int]:
        """Return aggregated SLA counts across the full ticket dataset for a tenant.

        Counts are bucketed as:
          - breached: open, deadline set, deadline < now
          - at_risk : open, deadline set, now < deadline <= now + 4h
          - on_track: resolved OR no deadline OR deadline > now + 4h
          - total_tickets: all tickets for the tenant
        """
        now = datetime.now(UTC)
        at_risk_threshold = now + timedelta(hours=4)

        base_filter = and_(TicketModel.tenant_id == tenant_id)

        # breached
        breached_filter = and_(
            base_filter,
            TicketModel.resolved_at.is_(None),
            TicketModel.response_deadline.is_not(None),
            TicketModel.response_deadline < now,
        )
        breached_count = await self._session.scalar(
            select(func.count(TicketModel.id)).where(breached_filter)
        )

        # at_risk
        at_risk_filter = and_(
            base_filter,
            TicketModel.resolved_at.is_(None),
            TicketModel.response_deadline.is_not(None),
            TicketModel.response_deadline > now,
            TicketModel.response_deadline <= at_risk_threshold,
        )
        at_risk_count = await self._session.scalar(
            select(func.count(TicketModel.id)).where(at_risk_filter)
        )

        # total
        total_count = await self._session.scalar(
            select(func.count(TicketModel.id)).where(base_filter)
        )

        on_track_count = (total_count or 0) - (breached_count or 0) - (at_risk_count or 0)

        return {
            "breached": breached_count or 0,
            "at_risk": at_risk_count or 0,
            "on_track": on_track_count,
            "total_tickets": total_count or 0,
        }

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
