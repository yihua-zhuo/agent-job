"""Notifications router — /api/v1/notifications and /api/v1/reminders endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps service return values in success envelopes.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.notification_service import NotificationService

notifications_router = APIRouter(prefix="/api/v1", tags=["notifications"])


def _paginated_dicts(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class NotificationCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    notification_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    related_type: str | None = Field(None, max_length=50)
    related_id: int | None = Field(None, ge=1)


class PreferencesData(BaseModel):
    email: bool = True
    sms: bool = False
    in_app: bool = True
    push: bool = False


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str | None = None
    remind_at: str = Field(..., description="ISO 8601 datetime string")
    related_type: str | None = Field(None, max_length=50)
    related_id: int | None = Field(None, ge=1)


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------


@notifications_router.get(
    "/notifications",
    summary="List notifications for current user",
)
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List notifications for the authenticated user with optional unread filter."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    items, total = await svc.get_user_notifications(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    return _paginated_dicts(items, total, page, page_size)


@notifications_router.post(
    "/notifications/send",
    summary="Send a notification to a user",
)
async def send_notification(
    body: NotificationCreate,
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Send a notification to a specific user (admin or system action)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.send_notification(
        user_id=body.user_id,
        notification_type=body.notification_type,
        title=body.title,
        content=body.content,
        tenant_id=current_user.tenant_id,
        related_type=body.related_type,
        related_id=body.related_id,
    )
    return {"success": True, "data": data, "message": "通知发送成功"}


@notifications_router.put(
    "/notifications/{notification_id}/read",
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: int = Path(..., ge=1),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Mark a specific notification as read."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.mark_as_read(notification_id, tenant_id=current_user.tenant_id)
    return {"success": True, "data": data, "message": "通知已标记为已读"}


@notifications_router.post(
    "/notifications/mark-all-read",
    summary="Mark all notifications as read for current user",
)
async def mark_all_notifications_read(
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Mark all unread notifications as read for the authenticated user."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.mark_all_as_read(current_user.user_id, tenant_id=current_user.tenant_id)
    return {"success": True, "data": data, "message": "所有通知已标记为已读"}


@notifications_router.delete(
    "/notifications/{notification_id}",
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: int = Path(..., ge=1),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a specific notification."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.delete_notification(notification_id, tenant_id=current_user.tenant_id)
    return {"success": True, "data": data, "message": "通知已删除"}


@notifications_router.get(
    "/notifications/preferences",
    summary="Get notification preferences for current user",
)
async def get_notification_preferences(
    current_user: AuthContext = Depends(require_auth),
):
    """Get the current user's notification preferences (stored per user)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    # TODO: notification_preferences table not yet in schema
    return {"success": True, "data": PreferencesData(email=True, sms=False, in_app=True, push=False).model_dump()}


@notifications_router.put(
    "/notifications/preferences",
    summary="Update notification preferences for current user",
)
async def update_notification_preferences(
    body: PreferencesData,
    current_user: AuthContext = Depends(require_auth),
):
    """Update the current user's notification preferences."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    # TODO: notification_preferences table not yet in schema
    return {"success": True, "data": body.model_dump()}


# ---------------------------------------------------------------------------
# Reminder endpoints
# ---------------------------------------------------------------------------


@notifications_router.post(
    "/reminders",
    summary="Create a reminder for current user",
)
async def create_reminder(
    body: ReminderCreate,
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a reminder for the authenticated user."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.create_reminder(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        title=body.title,
        content=body.content,
        remind_at=body.remind_at,
        related_type=body.related_type,
        related_id=body.related_id,
    )
    return {"success": True, "data": data, "message": "提醒创建成功"}


@notifications_router.get(
    "/reminders",
    summary="List reminders for current user",
)
async def list_reminders(
    upcoming_only: bool = Query(True),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List reminders for the authenticated user."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    reminders = await svc.get_reminders(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        upcoming_only=upcoming_only,
    )
    return {"success": True, "data": reminders}


@notifications_router.delete(
    "/reminders/{reminder_id}",
    summary="Cancel a reminder",
)
async def cancel_reminder(
    reminder_id: int = Path(..., ge=1),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Cancel (delete) a specific reminder."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    data = await svc.cancel_reminder(reminder_id, tenant_id=current_user.tenant_id)
    return {"success": True, "data": data, "message": "提醒已取消"}
