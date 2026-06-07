"""Automation execution log ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
    tenant_id: Mapped[int] = mapped_column(
        # Data-integrity note — 0-sentinel for system-owned rows:
        # A plain integer column (no FK constraint) is used because system rows
        # carry tenant_id=0, which has no corresponding entry in tenants.id.
        # This is an intentional design trade-off: referential integrity for
        # normal (tenant_id>0) rows is enforced at the application/service
        # layer, while system rows bypass the constraint by design.
        # Callers MUST explicitly pass tenant_id=0 for system rows; omitting
        # the parameter will raise an IntegrityError rather than silently
        # defaulting.
        Integer,
        default=0,
        nullable=False,
        index=True,
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_context: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

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
