"""Ticket reply ORM model."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class TicketReplyModel(Base):
    """Ticket reply entity mapped to the `ticket_replies` table."""

    __tablename__ = "ticket_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "is_internal": self.is_internal,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }