"""Notification service for CRM system - async PostgreSQL via SQLAlchemy."""
from typing import List, Dict, Optional
from datetime import datetime, UTC

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.response import ApiResponse, PaginatedData


class NotificationService:
    """通知服务 — 支持多渠道发送、通知模板、优先级队列、发送状态追踪。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._require_session()

    def _require_session(self):
        """Guard: raise if no session is injected."""
        if self.session is None:
            raise TypeError(
                "NotificationService requires an injected AsyncSession; "
                "construct with NotificationService(async_session)."
            )

    # -------------------------------------------------------------------------
    # Core delivery
    # -------------------------------------------------------------------------

    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        tenant_id: int = 0,
        related_type: Optional[str] = None,
        related_id: Optional[int] = None,
    ) -> ApiResponse[Dict]:
        """发送通知（当前实现：存储到数据库 in-app 通知）。"""

        now = datetime.now(UTC)
        result = await self.session.execute(
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

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    async def get_user_notifications(
        self,
        user_id: int,
        tenant_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """获取用户通知列表（支持分页和未读过滤，多租户隔离）。"""

        count_sql = (
            "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_read = false"
            if unread_only
            else "SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND tenant_id = :tenant_id"
        )
        total_result = await self.session.execute(text(count_sql), {"user_id": user_id, "tenant_id": tenant_id})
        total = total_result.fetchone()[0]

        offset = (page - 1) * page_size
        if unread_only:
            fetch_sql = text("""
                SELECT id, tenant_id, user_id, type, title, content, is_read,
                       related_type, related_id, created_at
                FROM notifications
                WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_read = false
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
        else:
            fetch_sql = text("""
                SELECT id, tenant_id, user_id, type, title, content, is_read,
                       related_type, related_id, created_at
                FROM notifications
                WHERE user_id = :user_id AND tenant_id = :tenant_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
        rows = await self.session.execute(fetch_sql, {"user_id": user_id, "tenant_id": tenant_id, "limit": page_size, "offset": offset})
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

    async def mark_as_read(self, notification_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """标记通知已读（多租户隔离）。"""

        result = await self.session.execute(
            text("UPDATE notifications SET is_read = true WHERE id = :id AND tenant_id = :tenant_id RETURNING id, tenant_id, user_id, is_read"),
            {"id": notification_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if row is None:
            return ApiResponse.error(message="通知不存在", code=1404)
        return ApiResponse.success(data={"id": row[0], "tenant_id": row[1], "user_id": row[2], "is_read": row[3]}, message="通知已标记为已读")

    async def mark_all_as_read(self, user_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """标记所有通知已读（多租户隔离）。"""

        await self.session.execute(
            text("UPDATE notifications SET is_read = true WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_read = false"),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        count_result = await self.session.execute(
            text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_read = true"),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        count = count_result.fetchone()[0]
        return ApiResponse.success(data={"marked_count": count}, message=f"已标记{count}条通知为已读")

    async def delete_notification(self, notification_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """删除通知（多租户隔离）。"""

        result = await self.session.execute(
            text("DELETE FROM notifications WHERE id = :id AND tenant_id = :tenant_id RETURNING id"),
            {"id": notification_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if row is None:
            return ApiResponse.error(message="通知不存在", code=1404)
        return ApiResponse.success(data={"id": notification_id}, message="通知删除成功")

    async def get_unread_count(self, user_id: int, tenant_id: int) -> int:
        """获取未读通知数量（多租户隔离）。"""

        result = await self.session.execute(
            text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_read = false"),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        return result.fetchone()[0]

    # -------------------------------------------------------------------------
    # Reminders
    # -------------------------------------------------------------------------

    async def create_reminder(
        self,
        user_id: int,
        tenant_id: int,
        title: str,
        content: Optional[str] = None,
        remind_at=None,
        related_type: Optional[str] = None,
        related_id: Optional[int] = None,
    ) -> ApiResponse[Dict]:
        """创建提醒（多租户隔离）。"""

        if tenant_id is None or tenant_id == 0:
            raise ValueError("invalid tenant_id for create_reminder")
        now = datetime.now(UTC)
        remind_at_val = remind_at if isinstance(remind_at, datetime) else datetime.fromisoformat(str(remind_at))
        result = await self.session.execute(
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

    async def cancel_reminder(self, reminder_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """取消提醒（多租户隔离）。"""

        result = await self.session.execute(
            text("DELETE FROM reminders WHERE id = :id AND tenant_id = :tenant_id RETURNING id"),
            {"id": reminder_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if row is None:
            return ApiResponse.error(message="提醒不存在", code=1404)
        return ApiResponse.success(data={"id": reminder_id}, message="提醒已取消")

    async def get_reminders(self, user_id: int, tenant_id: int, upcoming_only: bool = True) -> List[Dict]:
        """获取用户的提醒列表（多租户隔离）。"""

        now = datetime.now(UTC)
        if upcoming_only:
            sql = text("""
                SELECT id, tenant_id, user_id, title, content, remind_at,
                       related_type, related_id, is_completed, created_at
                FROM reminders
                WHERE user_id = :user_id AND tenant_id = :tenant_id AND is_completed = false AND remind_at > :now
                ORDER BY remind_at ASC
            """)
            params = {"user_id": user_id, "tenant_id": tenant_id, "now": now}
        else:
            sql = text("""
                SELECT id, tenant_id, user_id, title, content, remind_at,
                       related_type, related_id, is_completed, created_at
                FROM reminders
                WHERE user_id = :user_id AND tenant_id = :tenant_id
                ORDER BY remind_at ASC
            """)
            params = {"user_id": user_id, "tenant_id": tenant_id}
        rows = await self.session.execute(sql, params)
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