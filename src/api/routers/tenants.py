"""Tenants router — /api/v1/tenants endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps successful results in {"success": True, "data": ..., "message": ...}.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.tenant_service import TenantService

tenants_router = APIRouter(prefix='/api/v1/tenants', tags=['tenants'])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field(..., min_length=1, max_length=50)
    admin_email: str | None = Field(None, max_length=255)
    settings: dict | None = None


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    plan: str | None = Field(None, min_length=1, max_length=50)
    status: str | None = None
    settings: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@tenants_router.post('', status_code=201)
async def create_tenant(
    body: TenantCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    data = await service.create_tenant(
        name=body.name,
        plan=body.plan,
        admin_email=body.admin_email,
        **({"settings": body.settings} if body.settings else {}),
    )
    return {"success": True, "data": data, "message": "租户创建成功"}


@tenants_router.get('/stats')
async def get_tenant_stats(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    data = await service.get_tenant_stats(ctx.tenant_id)
    return {"success": True, "data": data}


@tenants_router.get('/usage')
async def get_tenant_usage(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    data = await service.get_tenant_usage(ctx.tenant_id)
    return {"success": True, "data": data}


@tenants_router.get('/{tenant_id}')
async def get_tenant(
    tenant_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    data = await service.get_tenant(tenant_id)
    return {"success": True, "data": data}


@tenants_router.get('')
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    items, total = await service.list_tenants(page=page, page_size=page_size)
    return _paginated(items, total, page, page_size)


@tenants_router.put('/{tenant_id}')
async def update_tenant(
    tenant_id: int,
    body: TenantUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    update_data = body.model_dump(exclude_none=True)
    data = await service.update_tenant(tenant_id, **update_data)
    return {"success": True, "data": data, "message": "租户更新成功"}


@tenants_router.delete('/{tenant_id}')
async def delete_tenant(
    tenant_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TenantService(session)
    data = await service.delete_tenant(tenant_id)
    return {"success": True, "data": data, "message": "租户删除成功"}
