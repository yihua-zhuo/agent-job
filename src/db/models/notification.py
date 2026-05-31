"""Notification ORM model.

The NotificationModel maps to the `notifications` table and supports a
template-based notification system with per-channel delivery (in_app, email,
sms, push). Notifications are hard-deleted via the API — there is no soft-delete
or archived column. Archived notifications use status='archived' rather than a
deleted_at flag; this design reflects that notifications are ephemeral, low-stakes
events where compliance/retention requirements do not apply.

Schema migration (e7f6a5b3c12d) transformed the legacy columns (type, title, content,
is_read, related_type, related_id) into the new schema (channel, template, params_,
status, priority, delivered_at, read_at).
"""

import logging
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, and_, column, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from pkg.constants.notification_constants import PAYLOAD_PARAMS_ALLOWED_KEYS

logger = logging.getLogger(__name__)


class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table.

    No soft-delete column: notifications are hard-deleted via the API rather than
    archived. This is a deliberate choice — notifications are low-stakes, ephemeral
    events where retention/compliance requirements don't apply. Use archived status
    (status='archived') or add a deleted_at column if that requirement emerges.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Composite index for tenant + user + status queries.
        # tenant_id leads to support tenant-scoped queries efficiently.
        Index("ix_notifications_tenant_user_status", "tenant_id", "user_id", "status"),
        # Partial index for unread in-app notifications lookup.
        # Uses column() (string) rather than the model attribute because the partial
        # index WHERE clause requires a SQL expression that the mapped column reference
        # cannot express directly.
        Index(
            "ix_notifications_in_app_unread",
            "user_id",
            "tenant_id",
            postgresql_where=and_(
                column("channel") == "in_app",
                column("read_at").is_(None),
            ),
        ),
        # DB-level enforcement of the channel, priority, and status allow-lists.
        CheckConstraint(column("channel").in_(["in_app", "email", "sms", "push"]), name="ck_notifications_channel"),
        CheckConstraint(column("priority").in_(["low", "normal", "high", "urgent"]), name="ck_notifications_priority"),
        CheckConstraint(
            column("status").in_(["pending", "read", "archived", "delivered", "failed"]), name="ck_notifications_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Trailing underscore avoids collision with ORM/DB column names.
    # Serialized as 'params' in to_dict() for a cleaner API surface.
    # NOTE: If this attribute name changes, update the bind key in
    # tests/unit/domain_handlers/notification.py accordingly.
    payload_params: Mapped[dict | None] = mapped_column("params_", JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Nullable for legacy rows (pre-migration e7f6a5b3c12d). Set by the service
    # layer when status transitions to 'delivered'; not populated during normal
    # notification creation since delivery is handled asynchronously.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        # Allow-list filtering is applied on top-level keys via PAYLOAD_PARAMS_ALLOWED_KEYS.
        # Nested content (e.g. content field in payload_params) is intentionally exposed;
        # callers are responsible for their own PII-handling obligations.
        params = self.payload_params
        if params:
            unknown = set(params.keys()) - PAYLOAD_PARAMS_ALLOWED_KEYS
            if logger.isEnabledFor(logging.DEBUG) and unknown:
                logger.debug("Notification %d payload_params dropped keys: %s", self.id, sorted(unknown))
            params = {k: v for k, v in params.items() if k in PAYLOAD_PARAMS_ALLOWED_KEYS}
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "template": self.template,
            "params": params,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }


class NotificationAnalytics(Base):
    """Analytics record for a notification open/click event."""

    __tablename__ = "notification_analytics"
    __table_args__ = (
        Index("ix_notification_analytics_notification_tenant", "notification_id", "tenant_id"),
        CheckConstraint(
            column("channel").in_(["in_app", "email", "sms", "push"]),
            name="ck_notification_analytics_channel",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, server_default="email")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "notification_id": self.notification_id,
            "tenant_id": self.tenant_id,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "channel": self.channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
