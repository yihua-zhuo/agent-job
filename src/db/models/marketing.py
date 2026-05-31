"""Marketing (campaign) ORM models."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
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
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["CampaignEventModel"]] = relationship(
        "CampaignEventModel",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    triggers: Mapped[list["TriggerModel"]] = relationship(
        "TriggerModel",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "subject": self.subject,
            "content": self.content,
            "target_audience": self.target_audience,
            "trigger_type": self.trigger_type,
            "trigger_days": self.trigger_days,
            "created_by": self.created_by,
            "sent_count": self.sent_count or 0,
            "open_count": self.open_count or 0,
            "click_count": self.click_count or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


class CampaignEventModel(Base):
    """Campaign event entity mapped to the `campaign_events` table."""

    __tablename__ = "campaign_events"
    __table_args__ = (Index("ix_campaign_events_tenant_campaign", "tenant_id", "campaign_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
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


class TriggerModel(Base):
    """Trigger entity mapped to the `campaign_triggers` table."""

    __tablename__ = "campaign_triggers"
    __table_args__ = (Index("ix_campaign_triggers_tenant_campaign", "tenant_id", "campaign_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, default=lambda: dict(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    campaign: Mapped["CampaignModel | None"] = relationship(
        "CampaignModel",
        back_populates="triggers",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "type": self.type,
            "conditions": self.conditions or {},
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
