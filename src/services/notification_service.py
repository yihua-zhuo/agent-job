"""Notification service — DB-backed via SQLAlchemy async ORM."""
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel
from pkg.errors.app_exceptions import NotFoundException


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
        tenant_id: int = 0,
        **kwargs,
    ) -> NotificationModel:
        """发送通知"""
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=False,
            related_type=kwargs.get("related_type"),
            related_id=kwargs.get("related_id"),
            created_at=datetime.now(UTC),
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        await self.session.commit()
        return notification

    async def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
        tenant_id: int = 0,
    ) -> tuple[list[NotificationModel], int]:
        """获取用户通知列表"""
        conditions = [
            NotificationModel.tenant_id == tenant_id,
            NotificationModel.user_id == user_id,
        ]
        if unread_only:
            conditions.append(NotificationModel.is_read == False)  # noqa: E712

        count_result = await self.session.execute(
            select(func.count(NotificationModel.id)).where(and_(*conditions))
        )
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

    async def mark_as_read(self, notification_id: int, tenant_id: int = 0) -> NotificationModel:
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
            raise NotFoundException("通知")
        notification.is_read = True
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_all_as_read(self, user_id: int, tenant_id: int = 0) -> dict:
        """标记所有通知已读"""
        result = await self.session.execute(
            select(NotificationModel).where(
                and_(
                    NotificationModel.tenant_id == tenant_id,
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read == False,  # noqa: E712
                )
            )
        )
        unread = result.scalars().all()
        for n in unread:
            n.is_read = True
        await self.session.commit()
        return {"marked_count": len(unread)}

    async def delete_notification(self, notification_id: int, tenant_id: int = 0) -> dict:
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
            raise NotFoundException("通知")
        await self.session.commit()
        return {"id": notification_id}

    async def get_unread_count(self, user_id: int, tenant_id: int = 0) -> int:
        """获取未读通知数量"""
        result = await self.session.execute(
            select(func.count(NotificationModel.id)).where(
                and_(
                    NotificationModel.tenant_id == tenant_id,
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read == False,  # noqa: E712
                )
            )
        )
        return result.scalar_one()

    # -------------------------------------------------------------------------
    # Reminders
    # -------------------------------------------------------------------------

    async def create_reminder(
        self,
        user_id: int,
        title: str,
        content: str,
        remind_at: datetime,
        tenant_id: int = 0,
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
            created_at=datetime.now(UTC),
        )
        self.session.add(reminder)
        await self.session.flush()
        await self.session.refresh(reminder)
        await self.session.commit()
        return reminder

    async def cancel_reminder(self, reminder_id: int, tenant_id: int = 0) -> dict:
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
        await self.session.commit()
        return {"id": reminder_id}

    async def get_reminders(
        self, user_id: int, upcoming_only: bool = True, tenant_id: int = 0,
    ) -> list[ReminderModel]:
        """获取用户的提醒列表"""
        conditions = [
            ReminderModel.tenant_id == tenant_id,
            ReminderModel.user_id == user_id,
        ]
        if upcoming_only:
            conditions.append(ReminderModel.is_completed == False)  # noqa: E712
            conditions.append(ReminderModel.remind_at > datetime.now(UTC))

        result = await self.session.execute(
            select(ReminderModel)
            .where(and_(*conditions))
            .order_by(ReminderModel.remind_at)
        )
        return result.scalars().all()
