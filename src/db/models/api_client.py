"""API Client model for multi-algorithm JWT authentication."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ApiClientModel(Base):
    """API client entity for per-client JWT algorithm and scope management."""

    __tablename__ = "api_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Algorithm: HS256 / HS384 / HS512 / RS256 / RS384 / RS512 / ES256 / ES384 / ES512
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="HS256")
    # Symmetric key (encrypted stored) — for HS* algorithms
    secret_key: Mapped[str] = mapped_column(Text, nullable=True)
    # Public key — for RS*/ES* algorithms (server stores public key only)
    public_key: Mapped[str] = mapped_column(Text, nullable=True)
    # Scopes granted to this client, stored as JSON list
    scopes: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
