"""Marketing (campaign) ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class CampaignModel(Base):
    """Campaign entity mapped to the `campaigns` table."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="email", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trigger_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    events: Mapped[list["CampaignEventModel"]] = relationship(
        "CampaignEventModel",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "subject": self.subject,
            "content": self.content,
            "target_audience": self.target_audience,
            "trigger_type": self.trigger_type,
            "trigger_days": self.trigger_days,
            "created_by": self.created_by,
            "sent_count": self.sent_count,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CampaignEventModel(Base):
    """Campaign event entity mapped to the `campaign_events` table."""

    __tablename__ = "campaign_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    campaign: Mapped["CampaignModel"] = relationship(
        "CampaignModel",
        back_populates="events",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
