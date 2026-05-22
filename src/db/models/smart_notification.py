"""Smart notification ORM model."""

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Priority(enum.IntEnum):
    """Priority level for smart notifications."""

    urgent = 0
    normal = 1
    low = 2


class Channel(enum.IntEnum):
    """Delivery channel for smart notifications."""

    email = 0
    sms = 1
    push = 2
    in_app = 3


class Timing(enum.IntEnum):
    """Delivery timing for smart notifications."""

    immediate = 0
    batch = 1


class SmartNotificationModel(Base):
    """Smart notification entity mapped to the `smart_notifications` table."""

    __tablename__ = "smart_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    summarized_content: Mapped[str] = mapped_column(String(1024), nullable=False)
    priority: Mapped[int] = mapped_column(SQLEnum(Priority, name="smart_notification_priority", native_enum=True), nullable=False, default=Priority.normal)
    channel: Mapped[int] = mapped_column(SQLEnum(Channel, name="smart_notification_channel", native_enum=True), nullable=False, default=Channel.email)
    timing: Mapped[int] = mapped_column(SQLEnum(Timing, name="smart_notification_timing", native_enum=True), nullable=False, default=Timing.immediate)
    recipient_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "summarized_content": self.summarized_content,
            "priority": self.priority,
            "channel": self.channel,
            "timing": self.timing,
            "recipient_filter": self.recipient_filter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

