"""Notification preference ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationPreferenceModel(Base):
    """Notification preference entity mapped to the `notification_preferences` table."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_tenant_id", "tenant_id"),
        Index("ix_notification_preferences_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "channel": self.channel,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
