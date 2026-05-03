"""Automation rules and execution logs ORM models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AutomationRuleModel(Base):
    """User-defined automation rules stored in DB."""

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "trigger_event": self.trigger_event,
            "conditions": self.conditions or [],
            "actions": self.actions or [],
            "enabled": self.enabled,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AutomationLogModel(Base):
    """Execution log for automation rules."""

    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
