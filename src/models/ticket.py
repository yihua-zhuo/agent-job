from dataclasses import dataclass
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
    id: Optional[int]
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    channel: TicketChannel
    customer_id: int
    assigned_to: Optional[int]
    sla_level: SLALevel
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    first_response_at: Optional[datetime]
    response_deadline: Optional[datetime]

    def check_sla_breach(self) -> bool:
        """检查是否SLA超时"""
        if self.resolved_at:
            return False
        if self.response_deadline is None:
            return False
        return datetime.now() > self.response_deadline


@dataclass
class TicketReply:
    id: Optional[int]
    ticket_id: int
    content: str
    is_internal: bool  # 内部备注，不对客户可见
    created_by: int
    created_at: datetime


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
