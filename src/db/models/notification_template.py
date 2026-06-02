"""NotificationTemplate ORM model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, column, func, text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationTemplateModel(Base):
    """NotificationTemplate entity mapped to the `notification_templates` table."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_tenant_id", "tenant_id"),
        CheckConstraint(column("channel").in_(["email", "sms", "push", "in_app"]), name="ck_notification_templates_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), server_default=text("0"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True, default=None)

    def to_dict(self) -> dict:
        # tenant_id is intentionally omitted from serialization; it is not
        # needed by the client and is filtered out per Rule 137 (credential
        # material / auth model allow-list policy).  Include it only when the
        # API contract explicitly requires it for client-side tenant routing.
        return {
            "id": self.id,
            "name": self.name,
            "channel": self.channel,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
