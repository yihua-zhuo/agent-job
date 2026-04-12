from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict


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
    id: Optional[int]
    name: str
    description: Optional[str]
    trigger_type: TriggerType
    trigger_config: Dict  # 触发器配置
    actions: List[Dict]  # 执行动作列表
    conditions: List[Dict]  # 条件列表
    status: WorkflowStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


@dataclass
class WorkflowExecution:
    """工作流执行记录"""
    id: Optional[int]
    workflow_id: int
    trigger_type: str
    triggered_by: int
    started_at: datetime
    completed_at: Optional[datetime]
    status: str  # running, success, failed
    result: Optional[Dict]
