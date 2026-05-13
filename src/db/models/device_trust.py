"""DeviceTrust ORM model — tracks trusted devices for re-auth triggering."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DeviceTrustModel(Base):
    """Device trust entity — maps to the `device_trust` table."""

    __tablename__ = "device_trust"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trusted_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trusted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    trusted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_device_trust_fingerprint", "device_fingerprint"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_fingerprint": self.device_fingerprint,
            "device_name": self.device_name,
            "trusted_ip": self.trusted_ip,
            "last_ip": self.last_ip,
            "last_location": self.last_location,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "trusted_at": self.trusted_at.isoformat() if self.trusted_at else None,
            "trusted": bool(self.trusted),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }