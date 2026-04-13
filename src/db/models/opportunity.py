"""Opportunity ORM model."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class OpportunityModel(Base):
    """Opportunity entity mapped to the `opportunities` table."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), default="lead", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "name": self.name,
            "stage": self.stage,
            "amount": str(self.amount),
            "probability": self.probability,
            "expected_close_date": (
                self.expected_close_date.isoformat() if self.expected_close_date else None
            ),
            "owner_id": self.owner_id,
            "pipeline_id": self.pipeline_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }