"""租户管理服务"""
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import NotFoundException

# Module-level state for persistence across instances (since routers create fresh service per request)
_tenants_db: dict[int, dict[str, Any]] = {}
_tenant_counter = 0


class TenantService:
    """租户管理服务"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_tenant(self, name: str, plan: str, admin_email: str, tenant_id: int = 0) -> dict:
        global _tenant_counter
        _tenant_counter += 1
        now = datetime.utcnow().isoformat()
        tenant = {
            "id": _tenant_counter,
            "name": name,
            "plan": plan,
            "admin_email": admin_email,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "user_count": 0,
            "storage_used": 0,
            "api_calls": 0,
        }
        _tenants_db[_tenant_counter] = tenant
        return tenant

    async def get_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        if tenant.get("deleted_at"):
            raise NotFoundException(f"Tenant {tenant_id}")
        return tenant

    async def update_tenant(self, tenant_id: int, _tenant_id: int = 0, **kwargs) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        allowed_fields = {"name", "plan", "admin_email", "status"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                tenant[key] = value
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return tenant

    async def suspend_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        tenant["status"] = "suspended"
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return tenant

    async def delete_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        tenant["status"] = "deleted"
        tenant["deleted_at"] = datetime.utcnow().isoformat()
        tenant["updated_at"] = tenant["deleted_at"]
        return {"id": tenant_id}

    async def list_tenants(self, page: int = 1, page_size: int = 20, status: str | None = None, _tenant_id: int = 0) -> tuple[list, int]:
        tenants = [t for t in _tenants_db.values() if t["status"] != "deleted"]
        if status:
            tenants = [t for t in tenants if t["status"] == status]
        total = len(tenants)
        start = (page - 1) * page_size
        end = start + page_size
        return tenants[start:end], total

    async def get_tenant_stats(self, tenant_id: int = 0) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        return {
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }

    async def get_tenant_usage(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            raise NotFoundException(f"Tenant {tenant_id}")
        return {
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }
