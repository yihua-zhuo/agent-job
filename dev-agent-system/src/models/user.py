"""User model for CRM system."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Role(Enum):
    """User role enumeration (alias for UserRole)."""
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    VIEWER = "viewer"



class UserRole(Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    VIEWER = "viewer"


class UserStatus(Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


@dataclass
class User:
    """User entity representing a system user."""
    username: str
    email: str
    role: Role
    id: Optional[int] = None
    full_name: Optional[str] = None
    is_active: bool = True
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

    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value if isinstance(self.role, Role) else self.role,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Create user instance from dictionary."""
        role_value = data.get('role')
        if isinstance(role_value, str):
            role = Role(role_value)
        else:
            role = role_value or Role.VIEWER

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
            username=data['username'],
            email=data['email'],
            role=role,
            full_name=data.get('full_name'),
            is_active=data.get('is_active', True),
            created_at=created_at,
            updated_at=updated_at,
        )