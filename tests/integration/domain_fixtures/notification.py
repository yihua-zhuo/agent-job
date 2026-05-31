"""Notification-domain integration test helpers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel

__all__ = ["_seed_notification", "_seed_reminder"]


async def _seed_notification(
    session: AsyncSession,
    tenant_id: int,
    user_id: int,
    *,
    # Maps to NotificationModel.template.
    template_name: str = "default",
    channel: str = "in_app",
    params_: dict | None = None,
    status: str = "pending",
    priority: str = "normal",
) -> NotificationModel:
    """Seed a notification for integration tests."""
    notification = NotificationModel(
        tenant_id=tenant_id,
        user_id=user_id,
        channel=channel,
        template=template_name,
        params_=params_ or {},
        status=status,
        priority=priority,
        # created_at is handled by the server_default on the ORM column.
    )
    session.add(notification)
    await session.flush()
    return notification


async def _seed_reminder(
    session: AsyncSession,
    tenant_id: int,
    user_id: int,
    title: str,
    content: str,
    remind_at: datetime,
    *,
    related_type: str | None = None,
    related_id: int | None = None,
) -> ReminderModel:
    """Seed a reminder for integration tests."""
    reminder = ReminderModel(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        content=content,
        remind_at=remind_at,
        related_type=related_type,
        related_id=related_id,
        is_completed=False,
        # created_at is handled by the server_default on the ORM column.
    )
    session.add(reminder)
    await session.flush()
    return reminder
