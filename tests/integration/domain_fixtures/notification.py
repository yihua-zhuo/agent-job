"""Notification-domain integration test helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel


async def _seed_notification(
    session: AsyncSession,
    tenant_id: int,
    user_id: int,
    *,
    # 'title' param aligns with send_notification(template=title) semantics.
    # Maps to ORM 'template' column (backfill migration sets template=title).
    title: str = "default",
    channel: str = "in_app",
    payload_params: dict | None = None,
    status: str = "pending",
    priority: str = "normal",
) -> NotificationModel:
    """Seed a notification for integration tests."""
    from datetime import UTC, datetime

    notification = NotificationModel(
        tenant_id=tenant_id,
        user_id=user_id,
        channel=channel,
        template=title,
        payload_params=payload_params or {},
        status=status,
        priority=priority,
        created_at=datetime.now(UTC),
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
    """Seed a reminder for integration tests.

    Args:
        remind_at: Must be a timezone-aware datetime (UTC). Passing a naive datetime
            will raise an error in the DB layer on PostgreSQL due to mixed tz awareness.
    """
    if remind_at.tzinfo is None:
        raise ValueError("remind_at must be timezone-aware")
    from datetime import UTC

    reminder = ReminderModel(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        content=content,
        remind_at=remind_at,
        related_type=related_type,
        related_id=related_id,
        is_completed=False,
        created_at=datetime.now(UTC),
    )
    session.add(reminder)
    await session.flush()
    return reminder


__all__ = ["_seed_notification", "_seed_reminder"]
