from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"  # 等待用户回复
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketChannel(Enum):
    EMAIL = "email"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    PHONE = "phone"


class SLALevel(Enum):
    BASIC = "basic"      # 24h response
    STANDARD = "standard"  # 8h response
    PREMIUM = "premium"    # 4h response
    ENTERPRISE = "enterprise"  # 1h response


@dataclass
class Ticket:
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    channel: TicketChannel
    customer_id: int
    sla_level: SLALevel
    id: Optional[int] = None
    tenant_id: int = 0
    assigned_to: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    response_deadline: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = None
        if self.assigned_to is None:
            self.assigned_to = None
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def check_sla_breach(self) -> bool:
        """检查是否SLA超时"""
        if self.resolved_at:
            return False
        if self.response_deadline is None:
            return False
        return datetime.utcnow() > self.response_deadline


@dataclass
class TicketReply:
    ticket_id: int
    content: str
    is_internal: bool  # 内部备注，不对客户可见
    created_by: int
    id: Optional[int] = None
    tenant_id: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = None
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class SLAConfig:
    """SLA配置"""
    level: SLALevel
    first_response_hours: int
    resolution_hours: int


SLA_CONFIGS = {
    SLALevel.BASIC: SLAConfig(SLALevel.BASIC, 24, 72),
    SLALevel.STANDARD: SLAConfig(SLALevel.STANDARD, 8, 24),
    SLALevel.PREMIUM: SLAConfig(SLALevel.PREMIUM, 4, 8),
    SLALevel.ENTERPRISE: SLAConfig(SLALevel.ENTERPRISE, 1, 4),
}
