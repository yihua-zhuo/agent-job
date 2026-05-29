"""Customer enrichment ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CustomerEnrichmentModel(Base):
    """Third-party customer data enrichment record."""

    __tablename__ = "customer_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        # One enrichment record per provider per customer. Refresh scenarios are
        # handled by application logic (upsert / re-insert with new timestamps) rather
        # than updating the existing row, so this constraint prevents accidental overwrites.
        UniqueConstraint("tenant_id", "customer_id", name="uq_enrichment_tenant_customer"),
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_data_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        # Note: raw_data_json is included verbatim. Ensure the Clearbit payload
        # contains no credentials or sensitive data before serializing.
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "provider": self.provider,
            "raw_data_json": self.raw_data_json or {},
            "enriched_at": self.enriched_at.isoformat() if self.enriched_at else None,
            "next_refresh_at": self.next_refresh_at.isoformat() if self.next_refresh_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
