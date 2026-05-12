"""User model for CRM system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Role(Enum):
    """User role enumeration (alias for UserRole)."""

    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    VIEWER = "viewer"
    GUEST = "guest"
    USER = "user"


class UserRole(Enum):
    """User role enumeration."""

    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    VIEWER = "viewer"
    GUEST = "guest"
    USER = "user"


class UserStatus(Enum):
    """User status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    BANNED = "banned"


@dataclass
class User:
    """User entity representing a system user."""

    username: str
    email: str
    role: Role = Role.USER
    id: int | None = None
    tenant_id: int = 0
    full_name: str | None = None
    status: UserStatus = UserStatus.PENDING
    bio: str | None = None
    is_active: bool = True
    tags: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if self.full_name is None:
            self.full_name = None
        if self.is_active is None:
            self.is_active = True
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.tags is None:
            self.tags = []

    def is_active_user(self) -> bool:
        """Return True if user is active (status == ACTIVE)."""
        return self.status == UserStatus.ACTIVE

    def has_permission(self, required_role) -> bool:
        """Check if user has at least the required role permission."""
        role_hierarchy = [Role.VIEWER, Role.USER, Role.SUPPORT, Role.SALES, Role.MANAGER, Role.ADMIN]
        try:
            user_val = self.role.value if hasattr(self.role, "value") else self.role
            user_level = next(i for i, r in enumerate(role_hierarchy) if r.value == user_val)
        except (AttributeError, StopIteration):
            return False
        try:
            req_val = required_role.value if hasattr(required_role, "value") else required_role
            req_level = next(i for i, r in enumerate(role_hierarchy) if r.value == req_val)
        except (AttributeError, StopIteration):
            return False
        return user_level >= req_level

    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        role_val = self.role.value if hasattr(self.role, "value") else self.role
        status_val = self.status.value if hasattr(self.status, "value") else self.status
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": role_val,
            "tenant_id": self.tenant_id,
            "full_name": self.full_name,
            "status": status_val,
            "bio": self.bio,
            "is_active": self.is_active,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create user instance from dictionary."""
        role_value = data.get("role")
        if isinstance(role_value, str):
            try:
                role = UserRole(role_value)
            except ValueError:
                role = UserRole.USER
        elif hasattr(role_value, "value"):
            role = UserRole(role_value.value)
        else:
            role = UserRole.USER

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data.get("id"),
            username=data["username"],
            email=data["email"],
            role=role,
            status=UserStatus(data.get("status", "pending")) if data.get("status") else UserStatus.PENDING,
            full_name=data.get("full_name"),
            is_active=data.get("is_active", True),
            created_at=created_at,
            updated_at=updated_at,
        )
