"""Notifications router — /api/v1/notifications and /api/v1/reminders endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import Optional, List

from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth, AuthContext
from services.notification_service import NotificationService
from models.response import ResponseStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope

notifications_router = APIRouter(prefix="/api/v1", tags=["notifications"])


def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class NotificationCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    notification_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    related_type: Optional[str] = Field(None, max_length=50)
    related_id: Optional[int] = Field(None, ge=1)


class NotificationData(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    type: str
    title: str
    content: str
    is_read: bool
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    created_at: Optional[str] = None


class NotificationResponse(SuccessEnvelope):
    data: Optional[NotificationData] = None


class NotificationListData(BaseModel):
    items: List[NotificationData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class NotificationListResponse(SuccessEnvelope):
    data: NotificationListData


class NotificationMarkAllData(BaseModel):
    marked_count: int = Field(..., ge=0)


class NotificationMarkAllResponse(SuccessEnvelope):
    data: NotificationMarkAllData


class PreferencesData(BaseModel):
    email: bool = True
    sms: bool = False
    in_app: bool = True
    push: bool = False


class PreferencesResponse(SuccessEnvelope):
    data: PreferencesData


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    remind_at: str = Field(..., description="ISO 8601 datetime string")
    related_type: Optional[str] = Field(None, max_length=50)
    related_id: Optional[int] = Field(None, ge=1)


class ReminderData(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    title: str
    content: Optional[str] = None
    remind_at: str
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    is_completed: bool
    created_at: Optional[str] = None


class ReminderResponse(SuccessEnvelope):
    data: Optional[ReminderData] = None


class ReminderListData(BaseModel):
    items: List[ReminderData]
    total: int = Field(..., ge=0)


class ReminderListResponse(SuccessEnvelope):
    data: ReminderListData


class ReminderDeleteData(BaseModel):
    id: int


class ReminderDeleteResponse(SuccessEnvelope):
    data: ReminderDeleteData


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------


@notifications_router.get(
    "/notifications",
    response_model=NotificationListResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="List notifications for current user",
)
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """List notifications for the authenticated user with optional unread filter."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.get_user_notifications(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )

    items = [
        NotificationData(
            id=n["id"],
            tenant_id=n["tenant_id"],
            user_id=n["user_id"],
            type=n["type"],
            title=n["title"],
            content=n["content"],
            is_read=n["is_read"],
            related_type=n.get("related_type"),
            related_id=n.get("related_id"),
            created_at=n.get("created_at"),
        )
        for n in result.data.items
    ]
    return NotificationListResponse(
        data=NotificationListData(
            items=items,
            total=result.data.total,
            page=result.data.page,
            page_size=result.data.page_size,
            total_pages=result.data.total_pages,
            has_next=result.data.has_next,
            has_prev=result.data.has_prev,
        )
    )


@notifications_router.post(
    "/notifications/send",
    response_model=NotificationResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="Send a notification to a user",
)
async def send_notification(
    body: NotificationCreate,
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Send a notification to a specific user (admin or system action)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.send_notification(
        user_id=body.user_id,
        notification_type=body.notification_type,
        title=body.title,
        content=body.content,
        tenant_id=current_user.tenant_id,
        related_type=body.related_type,
        related_id=body.related_id,
    )

    n = result.data
    return NotificationResponse(
        data=NotificationData(
            id=n["id"],
            tenant_id=n["tenant_id"],
            user_id=n["user_id"],
            type=n["type"],
            title=n["title"],
            content=n["content"],
            is_read=n["is_read"],
            related_type=n.get("related_type"),
            related_id=n.get("related_id"),
            created_at=n.get("created_at"),
        )
    )


@notifications_router.put(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: int = Path(..., ge=1),
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Mark a specific notification as read."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.mark_as_read(notification_id, tenant_id=current_user.tenant_id)

    if result.status == ResponseStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail="通知不存在")

    d = result.data
    return NotificationResponse(
        data=NotificationData(
            id=d["id"],
            tenant_id=d.get("tenant_id", 0),
            user_id=d.get("user_id", 0),
            type="",
            title="",
            content="",
            is_read=True,
        )
    )


@notifications_router.post(
    "/notifications/mark-all-read",
    response_model=NotificationMarkAllResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="Mark all notifications as read for current user",
)
async def mark_all_notifications_read(
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Mark all unread notifications as read for the authenticated user."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.mark_all_as_read(current_user.user_id, tenant_id=current_user.tenant_id)

    return NotificationMarkAllResponse(
        data=NotificationMarkAllData(marked_count=result.data.get("marked_count", 0))
    )


@notifications_router.get(
    "/notifications/preferences",
    response_model=PreferencesResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="Get notification preferences for current user",
)
async def get_notification_preferences(
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Get the current user's notification preferences (stored per user)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    # TODO: notification_preferences table not yet in schema
    return PreferencesResponse(data=PreferencesData(email=True, sms=False, in_app=True, push=False))


@notifications_router.put(
    "/notifications/preferences",
    response_model=PreferencesResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="Update notification preferences for current user",
)
async def update_notification_preferences(
    body: PreferencesData,
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Update the current user's notification preferences."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    # TODO: notification_preferences table not yet in schema
    return PreferencesResponse(data=body)


# ---------------------------------------------------------------------------
# Reminder endpoints
# ---------------------------------------------------------------------------


@notifications_router.post(
    "/reminders",
    response_model=ReminderResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="Create a reminder for current user",
)
async def create_reminder(
    body: ReminderCreate,
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Create a reminder for the authenticated user."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.create_reminder(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        title=body.title,
        content=body.content,
        remind_at=body.remind_at,
        related_type=body.related_type,
        related_id=body.related_id,
    )

    r = result.data
    return ReminderResponse(
        data=ReminderData(
            id=r["id"],
            tenant_id=r["tenant_id"],
            user_id=r["user_id"],
            title=r["title"],
            content=r.get("content"),
            remind_at=r["remind_at"],
            related_type=r.get("related_type"),
            related_id=r.get("related_id"),
            is_completed=r.get("is_completed", False),
            created_at=r.get("created_at"),
        )
    )


@notifications_router.get(
    "/reminders",
    response_model=ReminderListResponse,
    responses={401: {"model": ErrorEnvelope}},
    summary="List reminders for current user",
)
async def list_reminders(
    upcoming_only: bool = Query(True),
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
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

    items = [
        ReminderData(
            id=r["id"],
            tenant_id=r["tenant_id"],
            user_id=r["user_id"],
            title=r["title"],
            content=r.get("content"),
            remind_at=r["remind_at"],
            related_type=r.get("related_type"),
            related_id=r.get("related_id"),
            is_completed=r.get("is_completed", False),
            created_at=r.get("created_at"),
        )
        for r in reminders
    ]
    return ReminderListResponse(data=ReminderListData(items=items, total=len(items)))


@notifications_router.delete(
    "/reminders/{reminder_id}",
    response_model=ReminderDeleteResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Cancel a reminder",
)
async def cancel_reminder(
    reminder_id: int = Path(..., ge=1),
    current_user: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    """Cancel (delete) a specific reminder."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    result = await svc.cancel_reminder(reminder_id, tenant_id=current_user.tenant_id)

    if result.status == ResponseStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail="提醒不存在")

    return ReminderDeleteResponse(data=ReminderDeleteData(id=reminder_id))