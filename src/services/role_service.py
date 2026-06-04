"""RoleService — thin facade over RBAC models for the management API.

This service provides the six methods called by ``RoleManagementRouter``:
list roles, create custom roles, get/update role permissions, assign roles
to users, and list all system permissions as resource/action pairs.

It delegates the heavy lifting to direct ORM queries on
``RoleModel`` / ``PermissionModel`` / ``RolePermissionModel`` / ``UserRoleModel``
rather than re-using ``RBACService`` so the new endpoints have a stable
contract that does not depend on ``RBACService`` internals.
"""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.rbac import PermissionModel, RoleModel, RolePermissionModel, UserRoleModel
from db.models.user import UserModel
from pkg.errors.app_exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from services.rbac_service import DEFAULT_PERMISSIONS


def _permission_pairs() -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for name, _display, _category in DEFAULT_PERMISSIONS:
        parts = name.split(":", 1)
        if len(parts) == 2:
            resource, action = parts
        else:
            resource, action = name, ""
        pairs.append({"resource": resource, "action": action})
    return pairs


class RoleService:
    """Service layer for the role-management API endpoints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_roles(self, tenant_id: int) -> list[RoleModel]:
        result = await self.session.execute(
            select(RoleModel)
            .where(or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0))
            .order_by(RoleModel.priority.desc(), RoleModel.id.asc())
        )
        return list(result.scalars().all())

    async def create_custom_role(
        self,
        tenant_id: int,
        name: str,
        permissions: list[str],
    ) -> RoleModel:
        existing = await self.session.execute(
            select(RoleModel).where(
                and_(RoleModel.tenant_id == tenant_id, RoleModel.name == name)
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictException(f"角色 '{name}' 在该租户中已存在")

        perm_result = await self.session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(permissions))
        )
        found = perm_result.scalars().all()
        found_names = {p.name for p in found}
        missing = set(permissions) - found_names
        if missing:
            raise ValidationException(f"不存在的权限: {', '.join(sorted(missing))}")

        role = RoleModel(
            tenant_id=tenant_id,
            name=name,
            display_name=name,
            description="",
            is_system=False,
            priority=0,
            created_at=datetime.now(UTC),
        )
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)

        for perm in found:
            self.session.add(RolePermissionModel(role_id=role.id, permission_id=perm.id))
        await self.session.flush()
        return role

    async def get_role_permissions(self, role_id: int, tenant_id: int) -> list[str]:
        role_check = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_check.scalar_one_or_none() is None:
            raise NotFoundException("角色")

        result = await self.session.execute(
            select(PermissionModel)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .where(RolePermissionModel.role_id == role_id)
            .order_by(PermissionModel.name)
        )
        return [p.name for p in result.scalars().all()]

    async def update_role_permissions(
        self,
        role_id: int,
        tenant_id: int,
        permissions: list[str],
    ) -> RoleModel:
        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        role = role_result.scalar_one_or_none()
        if role is None:
            raise NotFoundException("角色")
        if role.is_system:
            raise ForbiddenException("系统角色不可修改权限")

        # De-duplicate while preserving order — the input list is the caller's
        # data and we mutate the local variable, not the caller's list.
        permissions = list(dict.fromkeys(permissions))

        perm_result = await self.session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(permissions))
        )
        found = perm_result.scalars().all()
        found_names = {p.name for p in found}
        missing = set(permissions) - found_names
        if missing:
            raise ValidationException(f"不存在的权限: {', '.join(sorted(missing))}")

        await self.session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        for perm in found:
            self.session.add(RolePermissionModel(role_id=role_id, permission_id=perm.id))
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        tenant_id: int,
        granted_by: int = 0,
    ) -> dict:
        user_result = await self.session.execute(
            select(UserModel).where(
                and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            )
        )
        if user_result.scalar_one_or_none() is None:
            raise NotFoundException("用户")

        role_result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.id == role_id,
                    or_(RoleModel.tenant_id == tenant_id, RoleModel.tenant_id == 0),
                )
            )
        )
        if role_result.scalar_one_or_none() is None:
            raise NotFoundException("角色")

        existing = await self.session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id,
                    UserRoleModel.tenant_id == tenant_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            return {"user_id": user_id, "role_id": role_id, "already_assigned": True}

        self.session.add(
            UserRoleModel(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                granted_by=granted_by,
                granted_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
        return {"user_id": user_id, "role_id": role_id}

    async def list_all_permissions(self) -> list[dict[str, str]]:
        """Return the canonical system permission set as resource/action pairs.

        Sourced from the static ``DEFAULT_PERMISSIONS`` constant — these are
        the permissions defined at startup and are the complete set the system
        understands. DB-backed ``PermissionModel`` rows mirror this constant,
        so this is the authoritative list.
        """
        return _permission_pairs()
