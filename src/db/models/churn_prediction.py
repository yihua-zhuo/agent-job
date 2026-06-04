"""ChurnPrediction ORM model."""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChurnTier(StrEnum):
    """Churn tier classification using StrEnum semantics."""

    high = "high"
    medium = "medium"
    low = "low"


class ChurnPredictionModel(Base):
    """Churn prediction entity mapped to the `churn_predictions` table."""

    __tablename__ = "churn_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[ChurnTier | None] = mapped_column(
        sa.Enum(ChurnTier, name="churntier"), nullable=True
    )
    factors: Mapped[list[dict]] = mapped_column(JSONB, default=lambda: list(), nullable=False)
    recommended_actions: Mapped[list[dict]] = mapped_column(JSONB, default=lambda: list(), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="ck_churn_predictions_score_range"),
        Index("ix_churn_predictions_tenant_customer", "tenant_id", "customer_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "score": self.score,
            "tier": self.tier.value if isinstance(self.tier, ChurnTier) else self.tier,
            "factors": self.factors or [],
            "recommended_actions": self.recommended_actions or [],
            "model_version": self.model_version,
            "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
