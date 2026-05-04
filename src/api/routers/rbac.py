"""RBAC router — /api/v1/rbac/* role, permission, and user-role endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from services.rbac_service import RBACService

rbac_router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


def _status(status: ResponseStatus) -> int:
    return {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.CREATED: 201,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
    }.get(status, 400)


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
@rbac_router.post("/roles")
async def create_role(
    data: RoleCreate,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.create_role(
            tenant_id=ctx.tenant_id,
            name=data.name,
            display_name=data.display_name or data.name,
            description=data.description or "",
            priority=data.priority,
        )
        return result.to_dict(status_code=_status(result.status))


@rbac_router.get("/roles")
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_system: bool = Query(True),
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.list_roles(
            tenant_id=ctx.tenant_id,
            page=page,
            page_size=page_size,
            include_system=include_system,
        )
        return result.to_dict()


@rbac_router.get("/roles/{role_id}")
async def get_role(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.get_role(role_id=role_id, tenant_id=ctx.tenant_id)
        return result.to_dict(status_code=_status(result.status))


@rbac_router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        kwargs = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        result = await svc.update_role(role_id, tenant_id=ctx.tenant_id, **kwargs)
        return result.to_dict(status_code=_status(result.status))


@rbac_router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.delete_role(role_id=role_id, tenant_id=ctx.tenant_id)
        return result.to_dict(status_code=_status(result.status))


# Endpoints — Permissions
@rbac_router.get("/permissions")
async def list_permissions(
    category: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.list_permissions(category=category)
        return result.to_dict()


@rbac_router.get("/roles/{role_id}/permissions")
async def list_role_permissions(
    role_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.list_role_permissions(role_id=role_id, tenant_id=ctx.tenant_id)
        return result.to_dict(status_code=_status(result.status))


@rbac_router.put("/roles/{role_id}/permissions")
async def set_role_permissions(
    role_id: int,
    data: PermissionAssign,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.set_role_permissions(
            role_id=role_id,
            permission_names=data.permission_names,
            tenant_id=ctx.tenant_id,
        )
        return result.to_dict(status_code=_status(result.status))


# Endpoints — User role assignments
@rbac_router.post("/users/{user_id}/roles")
async def assign_role(
    user_id: int,
    data: RoleAssign,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.assign_role_to_user(
            user_id=user_id,
            role_id=data.role_id,
            tenant_id=ctx.tenant_id,
            granted_by=ctx.user_id,
        )
        return result.to_dict(status_code=_status(result.status))


@rbac_router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_role(
    user_id: int,
    role_id: int,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.revoke_role_from_user(
            user_id=user_id,
            role_id=role_id,
            tenant_id=ctx.tenant_id,
        )
        return result.to_dict(status_code=_status(result.status))


@rbac_router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.get_user_roles(user_id=user_id, tenant_id=ctx.tenant_id)
        return result.to_dict()


@rbac_router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.get_user_permissions(user_id=user_id, tenant_id=ctx.tenant_id)
        return result.to_dict()


@rbac_router.put("/users/{user_id}/roles")
async def set_user_roles(
    user_id: int,
    data: UserRolesSet,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.set_user_roles(
            user_id=user_id,
            role_ids=data.role_ids,
            tenant_id=ctx.tenant_id,
            granted_by=ctx.user_id,
        )
        return result.to_dict(status_code=_status(result.status))


@rbac_router.get("/roles/{role_id}/users")
async def list_users_with_role(
    role_id: int,
    ctx: AuthContext = Depends(require_auth),
):
    async with get_db() as session:
        svc = RBACService(session)
        result = await svc.list_users_with_role(role_id=role_id, tenant_id=ctx.tenant_id)
        return result.to_dict()
