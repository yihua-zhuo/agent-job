from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


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
    id: int | None = None
    subject: str = ""
    description: str = ""
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    channel: TicketChannel = TicketChannel.EMAIL
    customer_id: int = 0
    assigned_to: int | None = None
    sla_level: SLALevel = SLALevel.BASIC
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    first_response_at: datetime | None = None
    response_deadline: datetime | None = None

    def check_sla_breach(self) -> bool:
        """检查是否SLA超时"""
        if self.resolved_at:
            return False
        if not self.response_deadline:
            return False
        now = datetime.now(self.response_deadline.tzinfo) if self.response_deadline.tzinfo else datetime.now()
        return now > self.response_deadline


@dataclass
class TicketReply:
    id: int | None = None
    ticket_id: int = 0
    tenant_id: int = 0
    content: str = ""
    is_internal: bool = False
    created_by: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


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
