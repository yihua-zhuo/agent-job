"""Notification service for CRM system."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import NotFoundException

# Module-level state for placeholder service (shared across instances per-process)
_notifications_db: list[dict] = []
_reminders_db: list[dict] = []
_next_notification_id = 1
_next_reminder_id = 1


class NotificationService:
    """通知服务"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def send_notification(self, user_id: int, notification_type: str, title: str, content: str, tenant_id: int = 0, **kwargs) -> dict:
        """发送通知"""
        global _next_notification_id
        notification = {
            'id': _next_notification_id,
            'user_id': user_id,
            'type': notification_type,
            'title': title,
            'content': content,
            'is_read': False,
            'created_at': datetime.utcnow().isoformat(),
            'related_type': kwargs.get('related_type'),
            'related_id': kwargs.get('related_id'),
            'tenant_id': tenant_id,
        }
        _notifications_db.append(notification)
        _next_notification_id += 1
        return notification

    async def get_user_notifications(self, user_id: int, unread_only: bool = False, page: int = 1, page_size: int = 20, tenant_id: int = 0) -> tuple[list[dict], int]:
        """获取用户通知列表"""
        notifications = [n for n in _notifications_db if n['user_id'] == user_id]
        if unread_only:
            notifications = [n for n in notifications if not n['is_read']]

        notifications.sort(key=lambda x: x['created_at'], reverse=True)

        total = len(notifications)
        start = (page - 1) * page_size
        end = start + page_size
        items = notifications[start:end]

        return items, total

    async def mark_as_read(self, notification_id: int, tenant_id: int = 0) -> dict:
        """标记通知已读"""
        for notification in _notifications_db:
            if notification['id'] == notification_id:
                notification['is_read'] = True
                return {'id': notification_id}
        raise NotFoundException("通知")

    async def mark_all_as_read(self, user_id: int, tenant_id: int = 0) -> dict:
        """标记所有通知已读"""
        count = 0
        for notification in _notifications_db:
            if notification['user_id'] == user_id and not notification['is_read']:
                notification['is_read'] = True
                count += 1
        return {'marked_count': count}

    async def delete_notification(self, notification_id: int, tenant_id: int = 0) -> dict:
        """删除通知"""
        for i, notification in enumerate(_notifications_db):
            if notification['id'] == notification_id:
                _notifications_db.pop(i)
                return {'id': notification_id}
        raise NotFoundException("通知")

    def get_unread_count(self, user_id: int, tenant_id: int = 0) -> int:
        """获取未读通知数量"""
        return len([n for n in _notifications_db if n['user_id'] == user_id and not n['is_read']])

    async def create_reminder(self, user_id: int, title: str, content: str, remind_at: datetime, tenant_id: int = 0, related_type: str = None, related_id: int = None) -> dict:
        """创建提醒"""
        global _next_reminder_id
        reminder = {
            'id': _next_reminder_id,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'title': title,
            'content': content,
            'remind_at': remind_at.isoformat() if isinstance(remind_at, datetime) else remind_at,
            'related_type': related_type,
            'related_id': related_id,
            'is_completed': False,
            'created_at': datetime.utcnow().isoformat(),
        }
        _reminders_db.append(reminder)
        _next_reminder_id += 1
        return reminder

    async def cancel_reminder(self, reminder_id: int, tenant_id: int = 0) -> dict:
        """取消提醒"""
        for i, reminder in enumerate(_reminders_db):
            if reminder['id'] == reminder_id:
                _reminders_db.pop(i)
                return {'id': reminder_id}
        raise NotFoundException("提醒")

    async def get_reminders(self, user_id: int, upcoming_only: bool = True, tenant_id: int = 0) -> list[dict]:
        """获取用户的提醒列表"""
        reminders = [r for r in _reminders_db if r['user_id'] == user_id]

        if upcoming_only:
            now = datetime.utcnow()
            filtered = []
            for r in reminders:
                if r['is_completed']:
                    continue
                try:
                    remind_dt = datetime.fromisoformat(r['remind_at'])
                    # Ensure both are naive or both are aware for comparison
                    if remind_dt.tzinfo is not None and now.tzinfo is None:
                        now = remind_dt.replace(tzinfo=None)
                    elif remind_dt.tzinfo is None and now.tzinfo is not None:
                        remind_dt = remind_dt.replace(tzinfo=now.tzinfo)
                    if remind_dt > now:
                        filtered.append(r)
                except (ValueError, TypeError):
                    continue
            reminders = filtered

        reminders.sort(key=lambda x: x['remind_at'])
        return reminders
