"""ExportJob ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ExportJobModel(Base):
    """Export job entity mapped to the `export_jobs` table."""

    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    fields: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "entity_type": self.entity_type,
            "fields": self.fields or {},
            "filters": self.filters or {},
            "file_path": self.file_path,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
