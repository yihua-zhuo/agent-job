"""Notification service — DB-backed via SQLAlchemy async ORM."""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel
from db.models.user import UserModel
from pkg.constants.notification_constants import VALID_NOTIFICATION_TYPES, VALID_PRIORITIES
from pkg.errors.app_exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------

    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        tenant_id: int,
        **kwargs,
    ) -> NotificationModel:
        """Queue a notification for delivery.

        Creates a notification record with status='pending'. Actual delivery is
        handled asynchronously by a background worker. Flushes and refreshes
        the model; actual commit is owned by the router transaction boundary.
        """
        priority = kwargs.get("priority", "normal")
        if priority not in VALID_PRIORITIES:
            raise ValidationException(f"priority must be one of {sorted(VALID_PRIORITIES)}, got {priority!r}")
        if notification_type not in VALID_NOTIFICATION_TYPES:
            raise ValidationException(
                f"notification_type must be one of {sorted(VALID_NOTIFICATION_TYPES)}, got {notification_type!r}"
            )
        params = {"content": content}
        if kwargs.get("related_type") is not None:
            params["related_type"] = kwargs["related_type"]
        if kwargs.get("related_id") is not None:
            params["related_id"] = kwargs["related_id"]
        if len(json.dumps(params).encode()) > 4096:
            raise ValidationException("payload_params exceeds maximum size of 4096 bytes")
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=notification_type,
            template=title,
            payload_params=params,
            status="pending",
            priority=priority,
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_user_notifications(
        self,
        user_id: int,
        tenant_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NotificationModel], int]:
        """获取用户通知列表"""
        user_check = await self.session.execute(
            select(UserModel.id).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_check.scalar_one_or_none() is None:
            raise NotFoundException("User")
        conditions = [
            NotificationModel.tenant_id == tenant_id,
            NotificationModel.user_id == user_id,
        ]
        if unread_only:
            conditions.append(NotificationModel.read_at.is_(None))

        count_result = await self.session.execute(select(func.count(NotificationModel.id)).where(and_(*conditions)))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(NotificationModel)
            .where(and_(*conditions))
            .order_by(NotificationModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def mark_as_read(self, notification_id: int, tenant_id: int) -> NotificationModel:
        """标记通知已读"""
        result = await self.session.execute(
            select(NotificationModel).where(
                and_(
                    NotificationModel.id == notification_id,
                    NotificationModel.tenant_id == tenant_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundException("Notification")
        notification.read_at = datetime.now(UTC)
        notification.status = "read"
        await self.session.flush()
        return notification

    async def mark_all_as_read(self, user_id: int, tenant_id: int) -> dict:
        """标记所有通知已读"""
        user_check = await self.session.execute(
            select(UserModel.id).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_check.scalar_one_or_none() is None:
            raise NotFoundException("User")
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(NotificationModel)
            .where(
                and_(
                    NotificationModel.tenant_id == tenant_id,
                    NotificationModel.user_id == user_id,
                    NotificationModel.read_at.is_(None),
                )
            )
            .values(read_at=now, status="read")
        )
        marked_count = result.rowcount or 0
        return {"marked_count": marked_count}

    async def delete_notification(self, notification_id: int, tenant_id: int) -> NotificationModel:
        """删除通知"""
        result = await self.session.execute(
            select(NotificationModel).where(
                and_(
                    NotificationModel.id == notification_id,
                    NotificationModel.tenant_id == tenant_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundException("Notification")
        # Capture the domain object before deleting from session.
        domain = notification
        await self.session.execute(
            delete(NotificationModel).where(NotificationModel.id == notification_id)
        )
        await self.session.flush()
        return domain

    async def get_unread_count(self, user_id: int, tenant_id: int) -> int:
        """Get unread notification count for a user.

        Validates the user exists within the tenant before counting; returns 0
        if the user has no notifications (known users with zero notifications).
        Callers are responsible for validating the user first when a
        NotFoundException is preferred over a silent 0 for unknown users.
        """
        user_check = await self.session.execute(
            select(UserModel.id).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_check.scalar_one_or_none() is None:
            logger.info("User %d not found in tenant %d, returning 0 unread", user_id, tenant_id)
            return 0
        result = await self.session.execute(
            select(func.count(NotificationModel.id)).where(
                and_(
                    NotificationModel.tenant_id == tenant_id,
                    NotificationModel.user_id == user_id,
                    NotificationModel.read_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none() or 0

    # -------------------------------------------------------------------------
    # Reminders
    # -------------------------------------------------------------------------

    async def create_reminder(
        self,
        user_id: int,
        title: str,
        content: str,
        remind_at: datetime,
        tenant_id: int,
        related_type: str | None = None,
        related_id: int | None = None,
    ) -> ReminderModel:
        """创建提醒"""
        if isinstance(remind_at, str):
            remind_at = datetime.fromisoformat(remind_at)
        reminder = ReminderModel(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            content=content,
            remind_at=remind_at,
            related_type=related_type,
            related_id=related_id,
            is_completed=False,
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def cancel_reminder(self, reminder_id: int, tenant_id: int) -> ReminderModel:
        """取消提醒"""
        result = await self.session.execute(
            select(ReminderModel).where(
                and_(
                    ReminderModel.id == reminder_id,
                    ReminderModel.tenant_id == tenant_id,
                )
            )
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            raise NotFoundException("提醒")
        await self.session.execute(
            delete(ReminderModel).where(ReminderModel.id == reminder_id)
        )
        await self.session.flush()
        return reminder

    async def get_reminders(
        self,
        user_id: int,
        tenant_id: int,
        upcoming_only: bool = True,
    ) -> tuple[list[ReminderModel], int]:
        """获取用户的提醒列表"""
        user_check = await self.session.execute(
            select(UserModel.id).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_check.scalar_one_or_none() is None:
            raise NotFoundException("User")
        conditions = [
            ReminderModel.tenant_id == tenant_id,
            ReminderModel.user_id == user_id,
        ]
        if upcoming_only:
            conditions.append(ReminderModel.is_completed == False)  # noqa: E712
            conditions.append(ReminderModel.remind_at > datetime.now(UTC))

        count_result = await self.session.execute(select(func.count(ReminderModel.id)).where(and_(*conditions)))
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(ReminderModel).where(and_(*conditions)).order_by(ReminderModel.remind_at)
        )
        return result.scalars().all(), total
