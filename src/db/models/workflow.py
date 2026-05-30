"""Workflow ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WorkflowModel(Base):
    """Workflow entity mapped to the `workflows` table."""

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config or {},
            "actions": self.actions or [],
            "conditions": self.conditions or [],
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowExecutionModel(Base):
    """Workflow execution record mapped to the `workflow_executions` table."""

    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    triggered_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "trigger_type": self.trigger_type,
            "triggered_by": self.triggered_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": self.result,
        }


class WorkflowNodeModel(Base):
    """Workflow node record mapped to the `workflow_nodes` table."""

    __tablename__ = "workflow_nodes"
    __table_args__ = (
        Index("ix_workflow_nodes_tenant_id_workflow_id", "tenant_id", "workflow_id", unique=False),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(50), default="action", nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    execution_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "node_type": self.node_type,
            "definition_json": self.definition_json or {},
            "input": self.input or {},
            "output": self.output,
            "status": self.status,
            "execution_order": self.execution_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
