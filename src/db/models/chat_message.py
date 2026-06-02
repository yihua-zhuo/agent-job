"""Live chat message ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ChatMessageModel(Base):
    """Chat message within a session, mapped to the ``chat_messages`` table."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_chat_messages_tenant_session", "tenant_id", "session_id"),
        {"sqlite_autoincrement": True},
    )

    session: Mapped["ChatSessionModel"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ChatSessionModel",
        back_populates="messages",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
