"""Automation execution log ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AutomationLogModel(Base):
    """Execution log for automation rules."""

    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), server_default=text("0"), default=0, nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "tenant_id": self.tenant_id,
            "trigger_event": self.trigger_event,
            "trigger_context": self.trigger_context or {},
            "actions_executed": self.actions_executed or [],
            "status": self.status,
            "error_message": self.error_message,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }
