"""ChurnPrediction ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChurnPredictionModel(Base):
    """Churn prediction entity mapped to the `churn_predictions` table."""

    __tablename__ = "churn_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    factors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    recommended_actions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_churn_predictions_tenant_customer", "tenant_id", "customer_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "score": self.score,
            "tier": self.tier,
            "factors": self.factors or [],
            "recommended_actions": self.recommended_actions or [],
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
