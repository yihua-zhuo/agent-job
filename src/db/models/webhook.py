"""Webhook ORM models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WebhookModel(Base):
    """Webhook configuration mapped to the `webhooks` table."""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    __table_args__ = (Index("ix_webhooks_tenant_active", "tenant_id", "is_active"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "url": self.url,
            "events": self.events or [],
            "secret": "***" if self.secret else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookDeliveryModel(Base):
    """Webhook delivery record mapped to the `webhook_deliveries` table."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webhook_id: Mapped[int] = mapped_column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_delivery_next_retry",
            "next_retry_at",
            postgresql_where=text("(next_retry_at IS NOT NULL)"),
        ),
        Index("ix_webhook_deliveries_webhook_id", "webhook_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "tenant_id": self.tenant_id,
            "event_type": self.event_type,
            "payload": self.payload or {},
            "status": self.status,
            "response": self.response,
            "attempts": self.attempts,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "error_message": self.error_message,
        }
