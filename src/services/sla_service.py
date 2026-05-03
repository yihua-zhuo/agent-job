"""SLA service layer — SLA summary counts per tenant."""
from datetime import datetime, timedelta, UTC
from typing import Dict, Optional, TYPE_CHECKING

from models.response import ApiResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SLAService:
    """SLA summary counts backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: "AsyncSession"):
        self.session = session

    async def get_summary(self, tenant_id: int = 0) -> ApiResponse:
        """Compute SLA breach/at_risk/on_track counts for all tickets in tenant.

        - breached: response_deadline < now  AND ticket not resolved/closed
        - at_risk:   open ticket, response_deadline within 4 hours from now
        - on_track:  open ticket, response_deadline > 4 hours from now
          (resolved/closed tickets count as on_track)
        """
        if tenant_id == 0:
            return ApiResponse.error(message="无效的租户", code=1401)

        now = datetime.now(UTC)
        at_risk_threshold = now + timedelta(hours=4)

        # breached: open tickets past deadline
        breached_sql = """
            SELECT COUNT(*) FROM tickets
            WHERE tenant_id = :tenant_id
              AND resolved_at IS NULL
              AND closed_at IS NULL
              AND response_deadline < :now
        """
        # at_risk: open tickets with deadline within 4 hours
        at_risk_sql = """
            SELECT COUNT(*) FROM tickets
            WHERE tenant_id = :tenant_id
              AND resolved_at IS NULL
              AND closed_at IS NULL
              AND response_deadline >= :now
              AND response_deadline <= :at_risk_threshold
        """
        # on_track: open tickets with deadline > 4 hours
        on_track_sql = """
            SELECT COUNT(*) FROM tickets
            WHERE tenant_id = :tenant_id
              AND (
                resolved_at IS NOT NULL
                OR closed_at IS NOT NULL
                OR (response_deadline > :at_risk_threshold)
              )
        """
        from sqlalchemy import text

        params = {"tenant_id": tenant_id, "now": now, "at_risk_threshold": at_risk_threshold}

        breached_r = await self.session.execute(text(breached_sql), params)
        breached = breached_r.scalar() or 0

        at_risk_r = await self.session.execute(text(at_risk_sql), params)
        at_risk = at_risk_r.scalar() or 0

        on_track_r = await self.session.execute(text(on_track_sql), params)
        on_track = on_track_r.scalar() or 0

        total_tickets = breached + at_risk + on_track

        return ApiResponse.success(
            data={
                "breached": breached,
                "at_risk": at_risk,
                "on_track": on_track,
                "total_tickets": total_tickets,
            },
            message="",
        )
