"""Customer ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CustomerModel(Base):
    """Customer entity mapped to the `customers` table."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="lead", nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recycle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recycle_history: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # Index for (tenant, status) queries used in list_customers
        # Explicit index for mypy — omit if your DB dialect doesn't need it
        # Index(name="ix_customers_tenant_status", table_name="customers"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status,
            "owner_id": self.owner_id,
            "tags": self.tags or [],
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "recycle_count": self.recycle_count or 0,
            "recycle_history": self.recycle_history or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
