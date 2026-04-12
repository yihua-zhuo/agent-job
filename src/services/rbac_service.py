"""Role-Based Access Control (RBAC) service for permission management."""
from enum import Enum
from typing import Optional


class Permission(Enum):
    """Permission enumeration for CRM system actions."""
    # Customer permissions
    CUSTOMER_CREATE = "customer:create"
    CUSTOMER_READ = "customer:read"
    CUSTOMER_UPDATE = "customer:update"
    CUSTOMER_DELETE = "customer:delete"

    # Opportunity permissions
    OPPORTUNITY_CREATE = "opportunity:create"
    OPPORTUNITY_READ = "opportunity:read"
    OPPORTUNITY_UPDATE = "opportunity:update"
    OPPORTUNITY_DELETE = "opportunity:delete"

    # Admin permissions
    ADMIN_ALL = "admin:all"
    USER_MANAGE = "user:manage"


# All customer and opportunity permissions for role assignment
ALL_CUSTOMER_PERMISSIONS = [
    Permission.CUSTOMER_CREATE,
    Permission.CUSTOMER_READ,
    Permission.CUSTOMER_UPDATE,
    Permission.CUSTOMER_DELETE,
]

ALL_OPPORTUNITY_PERMISSIONS = [
    Permission.OPPORTUNITY_CREATE,
    Permission.OPPORTUNITY_READ,
    Permission.OPPORTUNITY_UPDATE,
    Permission.OPPORTUNITY_DELETE,
]

ALL_READ_PERMISSIONS = [
    Permission.CUSTOMER_READ,
    Permission.OPPORTUNITY_READ,
]


class RBACService:
    """Role-Based Access Control service mapping roles to permissions."""

    ROLE_PERMISSIONS = {
        'admin': [
            Permission.ADMIN_ALL,
            Permission.USER_MANAGE,
        ] + ALL_CUSTOMER_PERMISSIONS + ALL_OPPORTUNITY_PERMISSIONS,

        'manager': (
            ALL_READ_PERMISSIONS +
            [Permission.OPPORTUNITY_CREATE, Permission.OPPORTUNITY_UPDATE]
        ),

        'sales': (
            [Permission.CUSTOMER_READ, Permission.CUSTOMER_CREATE, Permission.CUSTOMER_UPDATE] +
            [Permission.OPPORTUNITY_READ, Permission.OPPORTUNITY_CREATE, Permission.OPPORTUNITY_UPDATE]
        ),

        'support': [
            Permission.CUSTOMER_READ,
            Permission.OPPORTUNITY_READ,
        ],

        'viewer': [
            Permission.CUSTOMER_READ,
            Permission.OPPORTUNITY_READ,
        ],
    }

    def has_permission(self, role: str, permission: Permission) -> bool:
        """Check if a role has a specific permission.

        Args:
            role: The role name to check.
            permission: The permission to verify.

        Returns:
            True if the role has the permission, False otherwise.
        """
        if role not in self.ROLE_PERMISSIONS:
            return False
        return permission in self.ROLE_PERMISSIONS[role]

    def get_role_permissions(self, role: str) -> list[Permission]:
        """Get all permissions for a given role.

        Args:
            role: The role name to get permissions for.

        Returns:
            List of Permission enums for the role, empty list if role not found.
        """
        return self.ROLE_PERMISSIONS.get(role, [])

    def check_permission_by_value(self, role: str, permission_value: str) -> bool:
        """Check if a role has a permission by its string value.

        Args:
            role: The role name to check.
            permission_value: The permission value string (e.g., 'customer:read').

        Returns:
            True if the role has the permission, False otherwise.
        """
        try:
            permission = Permission(permission_value)
            return self.has_permission(role, permission)
        except ValueError:
            return False
