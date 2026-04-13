"""Ticket ORM model."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TicketModel(Base):
    """Ticket entity mapped to the `tickets` table."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="email", nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sla_level: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def check_sla_breach(self) -> bool:
        """Check if SLA deadline has passed and ticket is unresolved."""
        if self.resolved_at:
            return False
        if self.response_deadline is None:
            return False
        return datetime.utcnow() > self.response_deadline

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "channel": self.channel,
            "customer_id": self.customer_id,
            "assigned_to": self.assigned_to,
            "sla_level": self.sla_level,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "first_response_at": self.first_response_at.isoformat() if self.first_response_at else None,
            "response_deadline": (
                self.response_deadline.isoformat() if self.response_deadline else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }