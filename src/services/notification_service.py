"""Notification service for CRM system."""
from typing import List, Dict, Optional
from datetime import datetime

from src.models.response import ApiResponse, PaginatedData


class NotificationService:
    """通知服务"""

    def __init__(self):
        self._notifications_db: List[Dict] = []
        self._reminders_db: List[Dict] = []
        self._next_notification_id = 1
        self._next_reminder_id = 1

    def send_notification(self, user_id: int, notification_type: str, title: str, content: str, **kwargs) -> ApiResponse[Dict]:
        """发送通知"""
        notification = {
            'id': self._next_notification_id,
            'user_id': user_id,
            'type': notification_type,
            'title': title,
            'content': content,
            'is_read': False,
            'created_at': datetime.utcnow().isoformat(),
            'related_type': kwargs.get('related_type'),
            'related_id': kwargs.get('related_id'),
        }
        self._notifications_db.append(notification)
        self._next_notification_id += 1
        return ApiResponse.success(data=notification, message='通知发送成功')

    def get_user_notifications(self, user_id: int, unread_only: bool = False, page: int = 1, page_size: int = 20) -> ApiResponse[PaginatedData[Dict]]:
        """获取用户通知列表"""
        notifications = [n for n in self._notifications_db if n['user_id'] == user_id]
        if unread_only:
            notifications = [n for n in notifications if not n['is_read']]

        notifications.sort(key=lambda x: x['created_at'], reverse=True)

        total = len(notifications)
        start = (page - 1) * page_size
        end = start + page_size
        items = notifications[start:end]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message=''
        )

    def mark_as_read(self, notification_id: int) -> ApiResponse[Dict]:
        """标记通知已读"""
        for notification in self._notifications_db:
            if notification['id'] == notification_id:
                notification['is_read'] = True
                return ApiResponse.success(data={'id': notification_id}, message='通知已标记为已读')
        return ApiResponse.error(message='通知不存在', code=1404)

    def mark_all_as_read(self, user_id: int) -> ApiResponse[Dict]:
        """标记所有通知已读"""
        count = 0
        for notification in self._notifications_db:
            if notification['user_id'] == user_id and not notification['is_read']:
                notification['is_read'] = True
                count += 1
        return ApiResponse.success(data={'marked_count': count}, message=f'已标记{count}条通知为已读')

    def delete_notification(self, notification_id: int) -> ApiResponse[Dict]:
        """删除通知"""
        for i, notification in enumerate(self._notifications_db):
            if notification['id'] == notification_id:
                self._notifications_db.pop(i)
                return ApiResponse.success(data={'id': notification_id}, message='通知删除成功')
        return ApiResponse.error(message='通知不存在', code=1404)

    def get_unread_count(self, user_id: int) -> int:
        """获取未读通知数量"""
        return len([n for n in self._notifications_db if n['user_id'] == user_id and not n['is_read']])

    def create_reminder(self, user_id: int, title: str, content: str, remind_at: datetime, related_type: str = None, related_id: int = None) -> ApiResponse[Dict]:
        """创建提醒"""
        reminder = {
            'id': self._next_reminder_id,
            'user_id': user_id,
            'title': title,
            'content': content,
            'remind_at': remind_at.isoformat() if isinstance(remind_at, datetime) else remind_at,
            'related_type': related_type,
            'related_id': related_id,
            'is_completed': False,
            'created_at': datetime.utcnow().isoformat(),
        }
        self._reminders_db.append(reminder)
        self._next_reminder_id += 1
        return ApiResponse.success(data=reminder, message='提醒创建成功')

    def cancel_reminder(self, reminder_id: int) -> ApiResponse[Dict]:
        """取消提醒"""
        for i, reminder in enumerate(self._reminders_db):
            if reminder['id'] == reminder_id:
                self._reminders_db.pop(i)
                return ApiResponse.success(data={'id': reminder_id}, message='提醒已取消')
        return ApiResponse.error(message='提醒不存在', code=1404)

    def get_reminders(self, user_id: int, upcoming_only: bool = True) -> List[Dict]:
        """获取用户的提醒列表"""
        reminders = [r for r in self._reminders_db if r['user_id'] == user_id]

        if upcoming_only:
            now = datetime.utcnow()
            reminders = [r for r in reminders if not r['is_completed'] and datetime.fromisoformat(r['remind_at']) > now]

        reminders.sort(key=lambda x: x['remind_at'])
        return reminders
