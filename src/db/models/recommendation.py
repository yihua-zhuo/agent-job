"""Recommendation and RiskSignal ORM models."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, func
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
    next_action: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[dict] = mapped_column(JSON, nullable=True)
    similar_deals: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_recommendations_tenant_opportunity", "tenant_id", "opportunity_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "next_action": NextAction(self.next_action).value,
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
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_factors: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_risk_signals_tenant_opportunity", "tenant_id", "opportunity_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "risk_level": RiskLevel(self.risk_level).value,
            "risk_factors": self.risk_factors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
