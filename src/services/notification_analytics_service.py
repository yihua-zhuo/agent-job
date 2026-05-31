"""Notification analytics service — track opens and compute open rates."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationAnalytics


class NotificationAnalyticsService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def track_open(self, notification_id: int, tenant_id: int, channel: str = "email") -> NotificationAnalytics:
        """Stamp opened_at on an existing analytics record, creating one if absent."""
        result = await self._session.execute(
            select(NotificationAnalytics).where(
                NotificationAnalytics.notification_id == notification_id,
                NotificationAnalytics.tenant_id == tenant_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            record = NotificationAnalytics(
                notification_id=notification_id,
                tenant_id=tenant_id,
                channel=channel,
                opened_at=datetime.now(UTC),
            )
            self._session.add(record)
            await self._session.flush()
            return record

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
