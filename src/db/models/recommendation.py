"""Recommendation and RiskSignal ORM models."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NextAction(StrEnum):
    """Recommended next action for an opportunity."""

    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    DEMO = "demo"
    PROPOSAL = "proposal"


class RiskLevel(StrEnum):
    """Risk level for an opportunity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationModel(Base):
    """AI-generated sales recommendation for an opportunity."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    next_action: Mapped[NextAction] = mapped_column(
        Enum(NextAction, name="next_action_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=True)
    similar_deals: Mapped[list] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_recommendations_tenant_opportunity", "tenant_id", "opportunity_id", unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "next_action": self.next_action.value if isinstance(self.next_action, NextAction) else NextAction(self.next_action).value,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "similar_deals": self.similar_deals,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RiskSignalModel(Base):
    """Risk assessment signal for an opportunity."""

    __tablename__ = "risk_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    risk_factors: Mapped[list] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_risk_signals_tenant_opportunity", "tenant_id", "opportunity_id", unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else RiskLevel(self.risk_level).value,
            "risk_factors": self.risk_factors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
