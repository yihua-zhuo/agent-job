"""Notification analytics service — track opens and compute open rates."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from db.models.notification import NotificationAnalytics
from pkg.errors.app_exceptions import NotFoundException


class NotificationAnalyticsService:
    def __init__(self, session):
        from sqlalchemy.ext.asyncio import AsyncSession

        if session is None:
            raise ValueError("session is required")
        self._session: AsyncSession = session

    async def track_open(self, notification_id: int, tenant_id: int, channel: str = "email") -> NotificationAnalytics:
        """Upsert an analytics record, stamping opened_at if not already set."""
        result = await self._session.execute(
            select(NotificationAnalytics).where(
                NotificationAnalytics.notification_id == notification_id,
                NotificationAnalytics.tenant_id == tenant_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            raise NotFoundException("Notification")

        if existing.opened_at is None:
            existing.opened_at = datetime.now(UTC)
        await self._session.flush()
        return existing

    async def get_open_rate(self, notification_id: int, tenant_id: int) -> float:
        """Return open rate (count of opened records) for a notification within a tenant."""
        result = await self._session.execute(
            select(func.count(NotificationAnalytics.id)).where(
                NotificationAnalytics.notification_id == notification_id,
                NotificationAnalytics.tenant_id == tenant_id,
                NotificationAnalytics.opened_at.isnot(None),
            )
        )
        count = result.scalar() or 0
        return float(count)
