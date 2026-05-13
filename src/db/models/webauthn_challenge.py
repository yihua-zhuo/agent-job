"""WebAuthnChallenge ORM model — temporary store for WebAuthn registration challenges."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WebAuthnChallengeModel(Base):
    """WebAuthn challenge entity — maps to the `webauthn_challenges` table.

    Challenges are single-use: consumed on finish_registration() or expire after TTL.
    """

    __tablename__ = "webauthn_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge: Mapped[str] = mapped_column(String(255), nullable=False)
    # challenge purpose: "registration" or "assertion"
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, default="registration")
    # Stored credential ID (for assertion verification)
    credential_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Device fingerprint at time of challenge creation
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Time when the challenge expires (default 60s for registration, 5min for assertion)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Whether the challenge has been consumed
    consumed: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)  # 0=active, 1=consumed
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_webauthn_challenges_user_id", "user_id"),
        Index("ix_webauthn_challenges_challenge", "challenge"),
        Index("ix_webauthn_challenges_expires", "expires_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "credential_id": self.credential_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "consumed": bool(self.consumed),
            "consumed_at": self.consumed_at.isoformat() if self.consumed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }