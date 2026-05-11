"""RBAC router — /api/v1/rbac/* role, permission, and user-role endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router serializes ORM objects via .to_dict(). Session injected via Depends(get_db).
"""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.rbac_service import RBACService

rbac_router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# Schemas
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = Field(None, max_length=100)
    description: str | None = Field("")
    priority: int = Field(0)


class RoleUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    description: str | None = Field(None)
    priority: int | None = Field(None)


class PermissionAssign(BaseModel):
    permission_names: list[str] = Field(..., min_items=1)


class RoleAssign(BaseModel):
    role_id: int


class UserRolesSet(BaseModel):
    role_ids: list[int] = Field(..., min_items=1)


# Endpoints — Roles
@rbac_router.post("/roles", status_code=201)
async def create_role(
    data: RoleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    role = await svc.create_role(
        tenant_id=ctx.tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description or "",
        priority=data.priority,
    )
    return {"success": True, "data": role.to_dict(), "message": "角色创建成功"}


@rbac_router.get("/roles")
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_system: bool = Query(True),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    roles, total = await svc.list_roles(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        include_system=include_system,
    )
    return _paginated(roles, total, page, page_size)


@rbac_router.get("/roles/{role_id}")
async def get_role(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    role = await svc.get_role(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": role.to_dict()}


@rbac_router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    kwargs = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    role = await svc.update_role(role_id, tenant_id=ctx.tenant_id, **kwargs)
    return {"success": True, "data": role.to_dict(), "message": "角色更新成功"}


@rbac_router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    deleted_id = await svc.delete_role(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"id": deleted_id}, "message": "角色删除成功"}


# Endpoints — Permissions
@rbac_router.get("/permissions")
async def list_permissions(
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    perms, total = await svc.list_permissions(category=category, page=page, page_size=page_size)
    return _paginated(perms, total, page, page_size)


@rbac_router.get("/roles/{role_id}/permissions")
async def list_role_permissions(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    perms = await svc.list_role_permissions(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [p.to_dict() for p in perms]}


@rbac_router.put("/roles/{role_id}/permissions")
async def set_role_permissions(
    role_id: int,
    data: PermissionAssign,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    perms = await svc.set_role_permissions(
        role_id=role_id,
        permission_names=data.permission_names,
        tenant_id=ctx.tenant_id,
    )
    return {
        "success": True,
        "data": {"role_id": role_id, "permissions": [p.name for p in perms]},
        "message": "权限分配成功",
    }


# Endpoints — User role assignments
@rbac_router.post("/users/{user_id}/roles")
async def assign_role(
    user_id: int,
    data: RoleAssign,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    result = await svc.assign_role_to_user(
        user_id=user_id,
        role_id=data.role_id,
        tenant_id=ctx.tenant_id,
        granted_by=ctx.user_id,
    )
    msg = "角色已分配" if result.get("already_assigned") else "角色分配成功"
    return {"success": True, "data": result, "message": msg}


@rbac_router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_role(
    user_id: int,
    role_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    result = await svc.revoke_role_from_user(
        user_id=user_id,
        role_id=role_id,
        tenant_id=ctx.tenant_id,
    )
    return {"success": True, "data": result, "message": "角色撤销成功"}


@rbac_router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    roles = await svc.get_user_roles(user_id=user_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [r.to_dict() for r in roles]}


@rbac_router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    perms = await svc.get_user_permissions(user_id=user_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": perms}


@rbac_router.put("/users/{user_id}/roles")
async def set_user_roles(
    user_id: int,
    data: UserRolesSet,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    role_ids = await svc.set_user_roles(
        user_id=user_id,
        role_ids=data.role_ids,
        tenant_id=ctx.tenant_id,
        granted_by=ctx.user_id,
    )
    return {"success": True, "data": {"user_id": user_id, "role_ids": role_ids}, "message": "用户角色更新成功"}


@rbac_router.get("/roles/{role_id}/users")
async def list_users_with_role(
    role_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RBACService(session)
    users = await svc.list_users_with_role(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [u.to_dict() for u in users]}
