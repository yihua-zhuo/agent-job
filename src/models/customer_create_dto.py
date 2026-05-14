"""Customer model for CRM system."""

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class CustomerStatus(Enum):
    """Customer status enumeration."""

    LEAD = "lead"
    OPPORTUNITY = "opportunity"
    CUSTOMER = "customer"
    INACTIVE = "inactive"


class CustomerCreateDTO(BaseModel):
    """Type-safe DTO for customer creation — maps to CustomerService.create_customer input.

    Fields mirror the acceptance criteria: name, email, phone, company, status, owner_id, tags.
    Uses Pydantic for runtime validation at the API boundary.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=False,
    )

    name: Annotated[str, Field(min_length=1, max_length=255)]
    email: Annotated[str, Field(min_length=1, max_length=255)]
    phone: str | None = None
    company: str | None = None
    status: str = "lead"
    owner_id: int = 0
    tags: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dict for CustomerService.create_customer."""
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status,
            "owner_id": self.owner_id,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomerCreateDTO":
        """Reconstruct from a raw dict (e.g. from parsed JSON body)."""
        name = data.get("name")
        email = data.get("email")
        if not name:
            raise ValueError("name is required and must be non-empty")
        if not email:
            raise ValueError("email is required and must be non-empty")
        return cls(
            name=name,
            email=email,
            phone=data.get("phone"),
            company=data.get("company"),
            status=data.get("status", "lead"),
            owner_id=data.get("owner_id", 0),
            tags=data.get("tags") or [],
        )


# Alias for existing code that imports CustomerStatus via the customer module
__all__ = ["CustomerCreateDTO", "CustomerStatus"]
