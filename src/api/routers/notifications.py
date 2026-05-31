"""Notifications router — /api/v1/notifications and /api/v1/reminders endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps service return values in success envelopes.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models.smart_notification import Channel, Priority, Timing
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.constants.notification_constants import VALID_NOTIFICATION_CHANNELS
from services.notification_routing_service import NotificationRoutingService
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
    notification_type: str = Field(..., description="One of: email, in_app, push, sms")
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    related_type: str | None = Field(None, max_length=50)
    related_id: int | None = Field(None, ge=1)

    @field_validator("notification_type")
    @classmethod
    def notification_type_must_be_valid(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_NOTIFICATION_CHANNELS:
            raise ValueError(f"notification_type must be one of {sorted(VALID_NOTIFICATION_CHANNELS)}, got {v!r}")
        return v_lower

    @field_validator("content")
    @classmethod
    def content_keys_must_be_allowed(cls, v: str) -> str:
        # At insert time, enforce PAYLOAD_PARAMS_ALLOWED_KEYS: only 'content' and
        # 'related_type'/'related_id' (optional fields) are allowed in the payload.
        # The title field carries the template name, so any additional top-level
        # keys passed via kwargs in send_notification are not relevant here.
# NOTE: 'password' in v.lower() is an intentional rough heuristic — real
        # credential-injection prevention belongs at the data layer.
        # This check intentionally does NOT catch api_key, secret, token, or similar
        # credential-adjacent strings; it only flags 'password' as a known sentinel.
        if v and "password" in v.lower():
            raise ValueError("content may not contain credential-class fields")
        return v


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


class SmartNotificationCreate(BaseModel):
    summarized_content: str = Field(..., min_length=1, max_length=1024)
    priority: int = Field(..., ge=0, le=2, description="0=urgent, 1=normal, 2=low")
    channel: int = Field(..., ge=0, le=3, description="0=email, 1=sms, 2=push, 3=in_app")
    timing: int = Field(..., ge=0, le=1, description="0=immediate, 1=batch")
    recipient_filter: dict | None = Field(None, description="Filter criteria for routing")

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v: int) -> int:
        if v not in {p.value for p in Priority}:
            raise ValueError(f"priority must be 0 (urgent), 1 (normal), or 2 (low), got {v}")
        return v

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: int) -> int:
        if v not in {c.value for c in Channel}:
            raise ValueError(f"channel must be 0 (email), 1 (sms), 2 (push), or 3 (in_app), got {v}")
        return v

    @field_validator("timing")
    @classmethod
    def timing_must_be_valid(cls, v: int) -> int:
        if v not in {t.value for t in Timing}:
            raise ValueError(f"timing must be 0 (immediate) or 1 (batch), got {v}")
        return v


_PRIORITY_MAP = {Priority.urgent: "urgent", Priority.normal: "normal", Priority.low: "low"}


def _priority_to_string(priority) -> str:
    """Convert a priority value (Priority enum, int, or string) to routing string."""
    if isinstance(priority, Priority):
        return _PRIORITY_MAP[priority]
    if isinstance(priority, int):
        # Plain int (e.g. 0, 1, 2) — convert via Priority IntEnum then map
        try:
            return _PRIORITY_MAP[Priority(priority)]
        except KeyError:
            return str(priority)
    return str(priority)


class _MockRoutingRecord:
    """Lightweight adapter that exposes priority as a string for NotificationRoutingService.

    NotificationRoutingService.route() expects priority to be a string
    ('urgent' | 'normal' | 'low'). SmartNotificationModel stores it as a Priority IntEnum.
    Rather than mutate the ORM object (which would corrupt in-memory state before
    serialization), we project it into a plain adapter.
    """

    def __init__(self, record):
        self.id = record.id
        self.tenant_id = record.tenant_id
        self.priority = _priority_to_string(record.priority)
        self.channel = record.channel
        self.timing = record.timing
        self.summarized_content = record.summarized_content
        self.recipient_filter = record.recipient_filter

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
    return _paginated_dicts([i.to_dict() for i in items], total, page, page_size)


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
        tenant_id=current_user.tenant_id,
        user_id=body.user_id,
        notification_type=body.notification_type,
        title=body.title,
        content=body.content,
        related_type=body.related_type,
        related_id=body.related_id,
    )
    return {"success": True, "data": data.to_dict(), "message": "通知发送成功"}


@notifications_router.post(
    "/notifications/smart",
    summary="Create a smart notification with routing",
)
async def create_smart_notification(
    body: SmartNotificationCreate,
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Accept a pre-classified event payload, persist a SmartNotification, and route it.

    The LLM classification integration is tracked in issue #41.
    """
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    record = await svc.create_smart_notification(
        summarized_content=body.summarized_content,
        priority=body.priority,
        channel=body.channel,
        timing=body.timing,
        tenant_id=current_user.tenant_id,
        recipient_filter=body.recipient_filter,
    )

    # Route via NotificationRoutingService to determine delivery channels
    routing_svc = NotificationRoutingService(session)
    routing_record = _MockRoutingRecord(record)
    deliveries = await routing_svc.route(routing_record, tenant_id=current_user.tenant_id)

    return {
        "success": True,
        "data": {
            "notification": record.to_dict(),
            "deliveries": [d.model_dump() for d in deliveries],
        },
        "message": "Smart notification created and routed",
    }


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
    return {"success": True, "data": data.to_dict(), "message": "通知已标记为已读"}


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
    return {"success": True, "data": {"marked_count": data.marked_count}, "message": "所有通知已标记为已读"}


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
    return {"success": True, "data": data.to_dict(), "message": "通知已删除"}


@notifications_router.get(
    "/notifications/preferences",
    summary="Get notification preferences for current user",
)
async def get_notification_preferences(
    current_user: AuthContext = Depends(require_auth),
):
    """Get the current user's notification preferences (stored per user)."""
    # TODO: implement notification_preferences table and wire to service
    raise HTTPException(status_code=501, detail="notification_preferences table not yet implemented")


@notifications_router.put(
    "/notifications/preferences",
    summary="Update notification preferences for current user",
)
async def update_notification_preferences(
    body: PreferencesData,
    current_user: AuthContext = Depends(require_auth),
):
    """Update the current user's notification preferences."""
    # TODO: implement notification_preferences table and wire to service
    raise HTTPException(status_code=501, detail="notification_preferences table not yet implemented")


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
    return {"success": True, "data": data.to_dict(), "message": "提醒创建成功"}


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
    reminders, total = await svc.get_reminders(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        upcoming_only=upcoming_only,
    )
    return {"success": True, "data": {"items": [r.to_dict() for r in reminders], "total": total}}


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
    return {"success": True, "data": data.to_dict(), "message": "提醒已取消"}
