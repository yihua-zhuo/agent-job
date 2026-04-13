"""Customer model for CRM system."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class CustomerStatus(Enum):
    """Customer status enumeration."""
    LEAD = "lead"
    OPPORTUNITY = "opportunity"
    CUSTOMER = "customer"
    INACTIVE = "inactive"


@dataclass
class Customer:
    """Customer entity representing a lead, opportunity, or actual customer."""
    name: str
    email: str
    owner_id: int
    tenant_id: int = 0
    id: Optional[int] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: CustomerStatus = CustomerStatus.LEAD
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if self.phone is None:
            self.phone = None
        if self.company is None:
            self.company = None
        if self.status is None:
            self.status = CustomerStatus.LEAD
        if not self.tags:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert customer to dictionary representation."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'status': self.status.value if isinstance(self.status, CustomerStatus) else self.status,
            'owner_id': self.owner_id,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Customer':
        """Create customer instance from dictionary."""
        status_value = data.get('status')
        if isinstance(status_value, str):
            status = CustomerStatus(status_value)
        else:
            status = status_value or CustomerStatus.LEAD

        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data.get('id'),
            tenant_id=data.get('tenant_id', 0),
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            company=data.get('company'),
            status=status,
            owner_id=data['owner_id'],
            tags=data.get('tags', []),
            created_at=created_at,
            updated_at=updated_at,
        )
