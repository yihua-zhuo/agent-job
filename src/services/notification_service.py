"""Notification service for CRM system."""
from datetime import datetime

from models.response import ApiResponse, PaginatedData, ResponseStatus

# Module-level state for placeholder service (shared across instances per-process)
_notifications_db: list[dict] = []
_reminders_db: list[dict] = []
_next_notification_id = 1
_next_reminder_id = 1


class NotificationService:
    """通知服务"""

    def __init__(self, session):
        self._session = session

    async def send_notification(self, user_id: int, notification_type: str, title: str, content: str, tenant_id: int = 0, **kwargs) -> ApiResponse:
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
        return ApiResponse(status=ResponseStatus.SUCCESS, data=notification, message='通知发送成功')

    async def get_user_notifications(self, user_id: int, unread_only: bool = False, page: int = 1, page_size: int = 20, tenant_id: int = 0) -> ApiResponse:
        """获取用户通知列表"""
        notifications = [n for n in _notifications_db if n['user_id'] == user_id]
        if unread_only:
            notifications = [n for n in notifications if not n['is_read']]

        notifications.sort(key=lambda x: x['created_at'], reverse=True)

        total = len(notifications)
        start = (page - 1) * page_size
        end = start + page_size
        items = notifications[start:end]

        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data=PaginatedData(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0,
            ),
            message='',
        )

    async def mark_as_read(self, notification_id: int, tenant_id: int = 0) -> ApiResponse:
        """标记通知已读"""
        for notification in _notifications_db:
            if notification['id'] == notification_id:
                notification['is_read'] = True
                return ApiResponse(status=ResponseStatus.SUCCESS, data={'id': notification_id}, message='通知已标记为已读')
        return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message='通知不存在')

    async def mark_all_as_read(self, user_id: int, tenant_id: int = 0) -> ApiResponse:
        """标记所有通知已读"""
        count = 0
        for notification in _notifications_db:
            if notification['user_id'] == user_id and not notification['is_read']:
                notification['is_read'] = True
                count += 1
        return ApiResponse(status=ResponseStatus.SUCCESS, data={'marked_count': count}, message=f'已标记{count}条通知为已读')

    async def delete_notification(self, notification_id: int, tenant_id: int = 0) -> ApiResponse:
        """删除通知"""
        for i, notification in enumerate(_notifications_db):
            if notification['id'] == notification_id:
                _notifications_db.pop(i)
                return ApiResponse(status=ResponseStatus.SUCCESS, data={'id': notification_id}, message='通知删除成功')
        return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message='通知不存在')

    def get_unread_count(self, user_id: int, tenant_id: int = 0) -> int:
        """获取未读通知数量"""
        return len([n for n in _notifications_db if n['user_id'] == user_id and not n['is_read']])

    async def create_reminder(self, user_id: int, title: str, content: str, remind_at: datetime, tenant_id: int = 0, related_type: str = None, related_id: int = None) -> ApiResponse:
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
        return ApiResponse(status=ResponseStatus.SUCCESS, data=reminder, message='提醒创建成功')

    async def cancel_reminder(self, reminder_id: int, tenant_id: int = 0) -> ApiResponse:
        """取消提醒"""
        for i, reminder in enumerate(_reminders_db):
            if reminder['id'] == reminder_id:
                _reminders_db.pop(i)
                return ApiResponse(status=ResponseStatus.SUCCESS, data={'id': reminder_id}, message='提醒已取消')
        return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message='提醒不存在')

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
