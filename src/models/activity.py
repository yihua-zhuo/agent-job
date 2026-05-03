"""Activity model for CRM system."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ActivityType(Enum):
    """Activity type enumeration."""
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"


@dataclass
class Activity:
    """Activity entity representing a customer/opportunity interaction."""
    customer_id: int
    type: ActivityType
    content: str
    created_by: int
    id: Optional[int] = None
    opportunity_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if self.opportunity_id is None:
            self.opportunity_id = None
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert activity to dictionary representation."""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'opportunity_id': self.opportunity_id,
            'type': self.type.value if isinstance(self.type, ActivityType) else self.type,
            'content': self.content,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Activity':
        """Create activity instance from dictionary."""
        type_value = data.get('type')
        if isinstance(type_value, str):
            activity_type = ActivityType(type_value)
        else:
            activity_type = type_value or ActivityType.NOTE

        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        return cls(
            id=data.get('id'),
            customer_id=data['customer_id'],
            opportunity_id=data.get('opportunity_id'),
            type=activity_type,
            content=data['content'],
            created_by=data['created_by'],
            created_at=created_at,
        )