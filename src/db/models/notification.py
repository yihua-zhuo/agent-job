"""Notification ORM model."""

import logging
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, and_, func, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from pkg.constants.notification_constants import PAYLOAD_PARAMS_ALLOWED_KEYS

logger = logging.getLogger(__name__)


class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table."""

    __tablename__ = "notifications"
    __table_args__ = (
        # Composite index for user + tenant + status queries.
        Index("ix_notifications_user_tenant_status", "user_id", "tenant_id", "status"),
        # Partial index for unread in-app notifications lookup.
        Index(
            "ix_notifications_in_app_unread",
            "user_id",
            "tenant_id",
            postgresql_where=and_(
                text("channel = 'in_app'"),
                text("read_at IS NULL"),
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Trailing underscore avoids collision with ORM/DB column names.
    # Serialized as 'params' in to_dict() for a cleaner API surface.
    payload_params: Mapped[dict | None] = mapped_column("params_", JSON, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Populated by the service layer when the notification is sent; intentionally
    # nullable here so legacy rows (pre-migration) remain valid.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        params = self.payload_params
        if params:
            unknown = set(params.keys()) - PAYLOAD_PARAMS_ALLOWED_KEYS
            if unknown:
                logger.warning("Notification %d payload_params dropped keys: %s", self.id, sorted(unknown))
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
