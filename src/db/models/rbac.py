"""Re-exports of RBAC models from the consolidated identity module."""

from db.models.identity import (
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserRoleModel,
)

__all__ = ["PermissionModel", "RoleModel", "RolePermissionModel", "UserRoleModel"]
