"""RoleManagementRouter — /api/v1/rbac/mgmt/* role and permission management endpoints.

Six endpoints specified in issue #642:
  - GET  /roles
  - POST /roles
  - GET  /roles/{role_id}/permissions
  - PUT  /roles/{role_id}/permissions
  - POST /users/{user_id}/role
  - GET  /permissions

This router is mounted under /api/v1/rbac/mgmt (a sub-prefix of the existing
rbac_router at /api/v1/rbac) so the two routers do not collide at FastAPI
registration time.

Note: CreateRoleRequest intentionally omits is_system, display_name, description,
and priority — only the minimum fields required by the issue are exposed. The
underlying RoleModel supports those columns, but management clients do not
require them in this iteration.
"""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from dependencies.rbac import require_permission
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.role_service import RoleService

role_management_router = APIRouter(prefix="/api/v1/rbac/mgmt", tags=["rbac-roles"])


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    permissions: list[str] = Field(..., min_length=0)


class UpdatePermissionsRequest(BaseModel):
    """At least one permission is required to avoid creating a zero-permission role."""

    permissions: list[str] = Field(..., min_length=1)


class AssignRoleRequest(BaseModel):
    role_id: int = Field(..., description="Role to assign to the user")


@role_management_router.get("/roles")
async def mgmt_list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    roles = await svc.list_roles(tenant_id=ctx.tenant_id)
    items = [r.to_dict() for r in roles]
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    total = len(items)
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "success": True,
        "data": {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@role_management_router.post("/roles", status_code=201)
async def mgmt_create_role(
    body: CreateRoleRequest,
    ctx: AuthContext = Depends(require_permission("admin", "all")),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    role = await svc.create_custom_role(
        tenant_id=ctx.tenant_id,
        name=body.name,
        permissions=body.permissions,
    )
    return {"success": True, "data": role.to_dict(), "message": "角色创建成功"}


@role_management_router.get("/roles/{role_id}/permissions")
async def mgmt_get_role_permissions(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    perms = await svc.get_role_permissions(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"role_id": role_id, "permissions": perms}}


@role_management_router.put("/roles/{role_id}/permissions")
async def mgmt_update_role_permissions(
    role_id: int,
    body: UpdatePermissionsRequest,
    ctx: AuthContext = Depends(require_permission("admin", "all")),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    role = await svc.update_role_permissions(
        role_id=role_id,
        tenant_id=ctx.tenant_id,
        permissions=body.permissions,
    )
    return {"success": True, "data": role.to_dict(), "message": "权限分配成功"}


@role_management_router.post("/users/{user_id}/role")
async def mgmt_assign_role(
    user_id: int,
    body: AssignRoleRequest,
    ctx: AuthContext = Depends(require_permission("admin", "all")),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    result = await svc.assign_role_to_user(
        user_id=user_id,
        role_id=body.role_id,
        tenant_id=ctx.tenant_id,
        granted_by=ctx.user_id,
    )
    msg = "角色已分配" if result.get("already_assigned") else "角色分配成功"
    return {"success": True, "data": result, "message": msg}


@role_management_router.get("/permissions")
async def mgmt_list_permissions(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    perms = await svc.list_all_permissions()
    return {"success": True, "data": perms}
