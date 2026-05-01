"""Notification service for CRM system - async PostgreSQL via SQLAlchemy."""
from typing import List, Dict, Optional
from datetime import datetime, UTC

from sqlalchemy import text, func, and_, or_

from db.connection import get_db_session
from models.response import ApiResponse, PaginatedData


class NotificationService:
    """通知服务"""

    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        **kwargs,
    ) -> ApiResponse[Dict]:
        """发送通知"""
        async with get_db_session() as session:
            tenant_id = kwargs.get("tenant_id", 0)
            related_type = kwargs.get("related_type")
            related_id = kwargs.get("related_id")
            now = datetime.now(UTC)
            result = await session.execute(
                text(
                    """
                    INSERT INTO notifications
                        (tenant_id, user_id, type, title, content, is_read, related_type, related_id, created_at)
                    VALUES
                        (:tenant_id, :user_id, :type, :title, :content, false, :related_type, :related_id, :now)
                    RETURNING id, tenant_id, user_id, type, title, content, is_read, related_type, related_id, created_at
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "type": notification_type,
                    "title": title,
                    "content": content,
                    "related_type": related_type,
                    "related_id": related_id,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            notification = {
                "id": row[0],
                "tenant_id": row[1],
                "user_id": row[2],
                "type": row[3],
                "title": row[4],
                "content": row[5],
                "is_read": row[6],
                "related_type": row[7],
                "related_id": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            }
            return ApiResponse.success(data=notification, message="通知发送成功")

    async def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """获取用户通知列表"""
        async with get_db_session() as session:
            # Count total
            count_sql = text(
                "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id"
            )
            params: Dict = {"user_id": user_id}
            if unread_only:
                count_sql = text(
                    "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = false"
                )
            total_result = await session.execute(count_sql, params)
            total = total_result.fetchone()[0]

            # Fetch page
            offset = (page - 1) * page_size
            fetch_sql = text(
                """
                SELECT id, tenant_id, user_id, type, title, content, is_read,
                       related_type, related_id, created_at
                FROM notifications
                WHERE user_id = :user_id
                """
                + (" AND is_read = false" if unread_only else "")
                + """
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            )
            rows = await session.execute(
                fetch_sql,
                {"user_id": user_id, "limit": page_size, "offset": offset},
            )
            items = [
                {
                    "id": r[0],
                    "tenant_id": r[1],
                    "user_id": r[2],
                    "type": r[3],
                    "title": r[4],
                    "content": r[5],
                    "is_read": r[6],
                    "related_type": r[7],
                    "related_id": r[8],
                    "created_at": r[9].isoformat() if r[9] else None,
                }
                for r in rows.fetchall()
            ]
            return ApiResponse.paginated(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                message="",
            )

    async def mark_as_read(self, notification_id: int) -> ApiResponse[Dict]:
        """标记通知已读"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    "UPDATE notifications SET is_read = true WHERE id = :id RETURNING id"
                ),
                {"id": notification_id},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message="通知不存在", code=1404)
            return ApiResponse.success(data={"id": notification_id}, message="通知已标记为已读")

    async def mark_all_as_read(self, user_id: int) -> ApiResponse[Dict]:
        """标记所有通知已读"""
        async with get_db_session() as session:
            await session.execute(
                text(
                    "UPDATE notifications SET is_read = true WHERE user_id = :user_id AND is_read = false"
                ),
                {"user_id": user_id},
            )
            await session.commit()
            count_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = true"
                ),
                {"user_id": user_id},
            )
            count = count_result.fetchone()[0]
            return ApiResponse.success(
                data={"marked_count": count}, message=f"已标记{count}条通知为已读"
            )

    async def delete_notification(self, notification_id: int) -> ApiResponse[Dict]:
        """删除通知"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    "DELETE FROM notifications WHERE id = :id RETURNING id"
                ),
                {"id": notification_id},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message="通知不存在", code=1404)
            return ApiResponse.success(
                data={"id": notification_id}, message="通知删除成功"
            )

    async def get_unread_count(self, user_id: int) -> int:
        """获取未读通知数量"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = false"
                ),
                {"user_id": user_id},
            )
            return result.fetchone()[0]

    async def create_reminder(
        self,
        user_id: int,
        title: str,
        content: str,
        remind_at: datetime,
        related_type: str = None,
        related_id: int = None,
    ) -> ApiResponse[Dict]:
        """创建提醒"""
        async with get_db_session() as session:
            tenant_id = 0  # derived from user lookup if needed
            now = datetime.now(UTC)
            remind_at_val = remind_at if isinstance(remind_at, datetime) else datetime.fromisoformat(str(remind_at))
            result = await session.execute(
                text(
                    """
                    INSERT INTO reminders
                        (tenant_id, user_id, title, content, remind_at, related_type, related_id, is_completed, created_at)
                    VALUES
                        (:tenant_id, :user_id, :title, :content, :remind_at, :related_type, :related_id, false, :now)
                    RETURNING id, tenant_id, user_id, title, content, remind_at, related_type, related_id, is_completed, created_at
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "title": title,
                    "content": content,
                    "remind_at": remind_at_val,
                    "related_type": related_type,
                    "related_id": related_id,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            reminder = {
                "id": row[0],
                "tenant_id": row[1],
                "user_id": row[2],
                "title": row[3],
                "content": row[4],
                "remind_at": row[5].isoformat() if row[5] else None,
                "related_type": row[6],
                "related_id": row[7],
                "is_completed": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            }
            return ApiResponse.success(data=reminder, message="提醒创建成功")

    async def cancel_reminder(self, reminder_id: int) -> ApiResponse[Dict]:
        """取消提醒"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    "DELETE FROM reminders WHERE id = :id RETURNING id"
                ),
                {"id": reminder_id},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message="提醒不存在", code=1404)
            return ApiResponse.success(data={"id": reminder_id}, message="提醒已取消")

    async def get_reminders(
        self, user_id: int, upcoming_only: bool = True
    ) -> List[Dict]:
        """获取用户的提醒列表"""
        async with get_db_session() as session:
            now = datetime.now(UTC)
            sql = text(
                """
                SELECT id, tenant_id, user_id, title, content, remind_at,
                       related_type, related_id, is_completed, created_at
                FROM reminders
                WHERE user_id = :user_id
                """
                + (" AND is_completed = false AND remind_at > :now" if upcoming_only else "")
                + """
                ORDER BY remind_at ASC
                """
            )
            params: Dict = {"user_id": user_id}
            if upcoming_only:
                params["now"] = now
            rows = await session.execute(sql, params)
            return [
                {
                    "id": r[0],
                    "tenant_id": r[1],
                    "user_id": r[2],
                    "title": r[3],
                    "content": r[4],
                    "remind_at": r[5].isoformat() if r[5] else None,
                    "related_type": r[6],
                    "related_id": r[7],
                    "is_completed": r[8],
                    "created_at": r[9].isoformat() if r[9] else None,
                }
                for r in rows.fetchall()
            ]
