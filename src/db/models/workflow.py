"""Workflow ORM models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WorkflowStatus(StrEnum):
    """Workflow lifecycle states.

    Used by services and callers to pass typed values; the model column
    is still String(50) (matching the existing migration) so the schema
    is unchanged. Application-side coercion via this enum prevents
    out-of-domain values from reaching the DB.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class WorkflowTriggerType(StrEnum):
    """Workflow trigger kinds."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"


class ExecutionStatus(StrEnum):
    """Workflow execution lifecycle states."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class NodeType(StrEnum):
    """Workflow node kinds."""

    ACTION = "action"
    CONDITION = "condition"
    TRIGGER = "trigger"


class NodeStatus(StrEnum):
    """Workflow node lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowModel(Base):
    """Workflow entity mapped to the `workflows` table.

    Cascade chain: deleting a tenant cascades to its workflows (tenant_id
    FK, ondelete=CASCADE) and then to child rows (WorkflowNodeModel and
    WorkflowExecutionModel) via their workflow_id FK. PostgreSQL
    handles the double-cascade without double-delete errors, but the
    deletion order is not guaranteed — operators relying on a specific
    sequence should pre-emptively delete child rows.
    """

    __tablename__ = "workflows"
    __table_args__ = (Index("ix_workflows_tenant_id_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual", server_default="manual", nullable=False)
    trigger_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    actions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="draft", server_default="draft", nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
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
    __table_args__ = (
        Index("ix_workflow_executions_workflow_id_tenant_id", "workflow_id", "tenant_id"),
        Index("ix_workflow_executions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual", server_default="manual", nullable=False)
    triggered_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", server_default="running", nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

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
        Index("ix_workflow_nodes_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), default="action", server_default="action", nullable=False)
    definition_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    input: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending", nullable=False)
    execution_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
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
