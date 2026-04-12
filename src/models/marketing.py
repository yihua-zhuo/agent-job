"""营销模型"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


class CampaignStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignType(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    AUTO = "auto"  # 自动化触达


class TriggerType(Enum):
    USER_REGISTER = "user_register"
    USER_INACTIVE = "user_inactive"
    PURCHASE_MADE = "purchase_made"
    CUSTOM = "custom"


@dataclass
class Campaign:
    id: Optional[int]
    name: str
    type: CampaignType
    status: CampaignStatus
    subject: Optional[str]  # Email subject
    content: str
    target_audience: str  # SQL or tag based
    trigger_type: Optional[TriggerType]
    trigger_days: Optional[int]  # e.g., 7 days inactive
    created_by: int
    created_at: datetime
    updated_at: datetime
    sent_count: int = 0
    open_count: int = 0
    click_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "subject": self.subject,
            "content": self.content,
            "target_audience": self.target_audience,
            "trigger_type": self.trigger_type.value if self.trigger_type else None,
            "trigger_days": self.trigger_days,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sent_count": self.sent_count,
            "open_count": self.open_count,
            "click_count": self.click_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        return cls(
            id=data.get("id"),
            name=data["name"],
            type=CampaignType(data["type"]),
            status=CampaignStatus(data["status"]),
            subject=data.get("subject"),
            content=data["content"],
            target_audience=data["target_audience"],
            trigger_type=TriggerType(data["trigger_type"]) if data.get("trigger_type") else None,
            trigger_days=data.get("trigger_days"),
            created_by=data["created_by"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            sent_count=data.get("sent_count", 0),
            open_count=data.get("open_count", 0),
            click_count=data.get("click_count", 0),
        )


@dataclass
class CampaignEvent:
    """用户行为事件"""
    id: Optional[int]
    campaign_id: int
    customer_id: int
    event_type: str  # sent, opened, clicked, bounced
    created_at: datetime
