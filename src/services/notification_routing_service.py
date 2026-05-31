from sqlalchemy.ext.asyncio import AsyncSession

from models.channel_delivery import ChannelDelivery
from pkg.errors.app_exceptions import ValidationException


class NotificationRoutingService:
    """Rule-based notification routing — maps SmartNotification priority to channel delivery list."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def route(self, notification, tenant_id: int) -> list[ChannelDelivery]:
        """Apply routing rules to produce a list of channel deliveries.

        Args:
            notification: SmartNotification object (or MagicMock for tests).
                Accessed via getattr for compatibility with ORM model post-#593.
            tenant_id: Tenant for multi-tenant isolation.

        Returns:
            list[ChannelDelivery] — one per applicable channel.

        Raises:
            ValidationException: if priority is not one of urgent | normal | low.
        """
        priority = getattr(notification, "priority", None)

        if priority == "urgent":
            user_id = getattr(notification, "user_id", None)
            email = getattr(notification, "email", None)
            return [
                ChannelDelivery(
                    channel="in_app",
                    target=str(user_id) if user_id else "",
                    priority=priority,
                    status="routed",
                    tenant_id=tenant_id,
                ),
                ChannelDelivery(
                    channel="email", target=email or "", priority=priority, status="routed", tenant_id=tenant_id
                ),
            ]

        if priority == "normal":
            user_id = getattr(notification, "user_id", None)
            if user_id is None:
                return []
            return [
                ChannelDelivery(
                    channel="in_app", target=str(user_id), priority=priority, status="routed", tenant_id=tenant_id
                ),
            ]

        if priority == "low":
            return [
                ChannelDelivery(
                    channel="batch", target="daily_digest", priority=priority, status="pending", tenant_id=tenant_id
                ),
            ]

        raise ValidationException(f"Unknown notification priority: {priority}")
