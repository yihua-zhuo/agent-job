"""TicketCategorization ORM model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TicketCategorizationModel(Base):
    """AI-generated ticket categorization result."""

    __tablename__ = "ticket_categorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggested_assignee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    categorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ticket_categorizations_tenant_ticket", "tenant_id", "ticket_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "ticket_id": self.ticket_id,
            "category_type": self.category_type,
            "priority": self.priority,
            "confidence": self.confidence,
            "reasons": self.reasons or {},
            "suggested_assignee_id": self.suggested_assignee_id,
            "suggested_team": self.suggested_team,
            "human_override": self.human_override if self.human_override is not None else False,
            "categorized_at": self.categorized_at.isoformat() if self.categorized_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
