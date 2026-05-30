"""Notification service — DB-backed via SQLAlchemy async ORM."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel
from db.models.user import UserModel
from pkg.constants.notification_constants import VALID_NOTIFICATION_TYPES, VALID_PRIORITIES
from pkg.errors.app_exceptions import NotFoundException, ValidationException


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
        """Send a notification.

        Flushes and refreshes the model; actual commit is owned by the router
        transaction boundary.
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
        await self.session.refresh(notification)
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

    async def delete_notification(self, notification_id: int, tenant_id: int) -> dict:
        """删除通知"""
        result = await self.session.execute(
            delete(NotificationModel).where(
                and_(
                    NotificationModel.id == notification_id,
                    NotificationModel.tenant_id == tenant_id,
                )
            )
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("Notification")
        await self.session.flush()
        return {"id": notification_id}

    async def get_unread_count(self, user_id: int, tenant_id: int) -> int:
        """Get unread notification count for a user.

        Silently returns 0 when the user does not exist (no-op). This is acceptable
        for a count endpoint but could hide upstream bugs if callers assume the user
        was validated before calling this method.
        """
        user_check = await self.session.execute(
            select(UserModel.id).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if user_check.scalar_one_or_none() is None:
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
        await self.session.refresh(reminder)
        return reminder

    async def cancel_reminder(self, reminder_id: int, tenant_id: int) -> dict:
        """取消提醒"""
        result = await self.session.execute(
            delete(ReminderModel).where(
                and_(
                    ReminderModel.id == reminder_id,
                    ReminderModel.tenant_id == tenant_id,
                )
            )
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("提醒")
        await self.session.flush()
        return {"id": reminder_id}

    async def get_reminders(
        self,
        user_id: int,
        tenant_id: int,
        upcoming_only: bool = True,
    ) -> tuple[list[ReminderModel], int]:
        """获取用户的提醒列表"""
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
