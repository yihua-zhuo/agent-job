from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class WorkflowStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class TriggerType(Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"  # 事件触发


@dataclass
class Workflow:
    id: int | None
    name: str
    description: str | None
    trigger_type: TriggerType
    trigger_config: dict  # 触发器配置
    actions: list[dict]  # 执行动作列表
    conditions: list[dict]  # 条件列表
    status: WorkflowStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


@dataclass
class WorkflowExecution:
    """工作流执行记录"""

    id: int | None
    workflow_id: int
    trigger_type: str
    triggered_by: int
    started_at: datetime
    completed_at: datetime | None
    status: str  # running, success, failed
    result: dict | None
