"""UserCredential ORM model — stores WebAuthn credentials (public keys)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserCredentialModel(Base):
    """WebAuthn credential entity — maps to the `user_credentials` table."""

    __tablename__ = "user_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # WebAuthn cred ID
    public_key: Mapped[str] = mapped_column(String(1024), nullable=False)  # Base64-encoded public key
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # WebAuthn counter to detect cloned credentials
    sign_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # UAF/U2F vs FIDO2
    authenticator_type: Mapped[str] = mapped_column(String(20), default="fido2", nullable=False)
    # WebAuthn transports (none, usb, nfc, ble, internal)
    transports: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Integer, default=1, nullable=False)  # 1=enabled, 0=disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_user_credentials_user_id", "user_id"),
        Index("ix_user_credentials_credential_id", "credential_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "credential_id": self.credential_id,
            "device_fingerprint": self.device_fingerprint,
            "device_name": self.device_name,
            "sign_count": self.sign_count,
            "authenticator_type": self.authenticator_type,
            "transports": self.transports,
            "enabled": bool(self.enabled),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }