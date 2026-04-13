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
    USER = "user"
    GUEST = "guest"
    VIEWER = "viewer"


class UserRole(Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    USER = "user"
    GUEST = "guest"
    VIEWER = "viewer"


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
    tenant_id: int = 0
    role: UserRole = UserRole.USER
    id: Optional[int] = None
    full_name: Optional[str] = None
    status: UserStatus = UserStatus.PENDING
    bio: Optional[str] = None
    tags: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if self.full_name is None:
            self.full_name = None
        if self.status is None:
            self.status = UserStatus.PENDING
        if self.bio is None:
            self.bio = None
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    @property
    def is_active(self) -> bool:
        """Check if user is active based on status."""
        return self.status == UserStatus.ACTIVE

    def has_permission(self, required_role) -> bool:
        """Check if user has permission for given role."""
        role_hierarchy = {
            'guest': 0,
            'viewer': 1,
            'user': 2,
            'support': 3,
            'sales': 4,
            'manager': 5,
            'admin': 6,
        }
        role_val = self.role.value if hasattr(self.role, 'value') else str(self.role)
        required_val = required_role.value if hasattr(required_role, 'value') else str(required_role)
        user_level = role_hierarchy.get(role_val, 0)
        required_level = role_hierarchy.get(required_val, 0)
        return user_level >= required_level

    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        def extract_value(val):
            if hasattr(val, 'value'):
                return val.value
            return val
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'tenant_id': self.tenant_id,
            'role': extract_value(self.role),
            'full_name': self.full_name,
            'status': extract_value(self.status),
            'bio': self.bio,
            'tags': self.tags,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Create user instance from dictionary."""
        role_value = data.get('role')
        if isinstance(role_value, str):
            role = UserRole(role_value)
        else:
            role = role_value or UserRole.VIEWER

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

        status_value = data.get('status')
        if isinstance(status_value, str):
            status = UserStatus(status_value)
        elif isinstance(status_value, UserStatus):
            status = status_value
        else:
            status = UserStatus.PENDING

        return cls(
            id=data.get('id'),
            username=data['username'],
            email=data['email'],
            tenant_id=data.get('tenant_id', 0),
            role=role,
            full_name=data.get('full_name'),
            status=status,
            bio=data.get('bio'),
            tags=data.get('tags', []),
            created_at=created_at,
            updated_at=updated_at,
        )
