"""Customer model for CRM system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


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
    id: int | None = None
    phone: str | None = None
    company: str | None = None
    status: CustomerStatus = CustomerStatus.LEAD
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert customer to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status.value if isinstance(self.status, CustomerStatus) else self.status,
            "owner_id": self.owner_id,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Customer":
        """Create customer instance from dictionary."""
        status_value = data.get("status")
        if isinstance(status_value, str):
            status = CustomerStatus(status_value)
        else:
            status = status_value or CustomerStatus.LEAD

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(UTC)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now(UTC)

        name = data.get("name")
        email = data.get("email")
        owner_id = data.get("owner_id", 0)

        if not name:
            raise ValueError("name is required and must be non-empty")
        if not email:
            raise ValueError("email is required and must be non-empty")

        return cls(
            id=data.get("id"),
            name=name,
            email=email,
            phone=data.get("phone"),
            company=data.get("company"),
            status=status,
            owner_id=owner_id,
            tags=data.get("tags") or [],
            created_at=created_at,
            updated_at=updated_at,
        )
