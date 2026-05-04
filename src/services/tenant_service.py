"""租户管理服务"""
from datetime import datetime
from typing import Any

from models.response import ApiResponse, ResponseStatus

# Module-level state for persistence across instances (since routers create fresh service per request)
_tenants_db: dict[int, dict[str, Any]] = {}
_tenant_counter = 0


class TenantService:
    """租户管理服务"""

    def __init__(self, session):
        self._session = session

    async def create_tenant(self, name: str, plan: str, admin_email: str, tenant_id: int = 0) -> ApiResponse:
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
        return ApiResponse(status=ResponseStatus.SUCCESS, data=tenant, message="租户创建成功")

    async def get_tenant(self, tenant_id: int, _tenant_id: int = 0) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        if tenant.get("deleted_at"):
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} has been deleted")
        return ApiResponse(status=ResponseStatus.SUCCESS, data=tenant, message="")

    async def update_tenant(self, tenant_id: int, _tenant_id: int = 0, **kwargs) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        allowed_fields = {"name", "plan", "admin_email", "status"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                tenant[key] = value
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return ApiResponse(status=ResponseStatus.SUCCESS, data=tenant, message="租户更新成功")

    async def suspend_tenant(self, tenant_id: int, _tenant_id: int = 0) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        tenant["status"] = "suspended"
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return ApiResponse(status=ResponseStatus.SUCCESS, data=tenant, message="租户已暂停")

    async def delete_tenant(self, tenant_id: int, _tenant_id: int = 0) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        tenant["status"] = "deleted"
        tenant["deleted_at"] = datetime.utcnow().isoformat()
        tenant["updated_at"] = tenant["deleted_at"]
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": tenant_id}, message="租户已删除")

    async def list_tenants(self, page: int = 1, page_size: int = 20, status: str | None = None, _tenant_id: int = 0) -> ApiResponse:
        tenants = [t for t in _tenants_db.values() if t["status"] != "deleted"]
        if status:
            tenants = [t for t in tenants if t["status"] == status]
        total = len(tenants)
        start = (page - 1) * page_size
        end = start + page_size
        return ApiResponse(status=ResponseStatus.SUCCESS, data={
            "items": tenants[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "has_next": end < total,
            "has_prev": page > 1,
        }, message="")

    async def get_tenant_stats(self, tenant_id: int = 0) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        return ApiResponse(status=ResponseStatus.SUCCESS, data={
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }, message="")

    async def get_tenant_usage(self, tenant_id: int, _tenant_id: int = 0) -> ApiResponse:
        tenant = _tenants_db.get(tenant_id)
        if not tenant:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message=f"Tenant {tenant_id} not found")
        return ApiResponse(status=ResponseStatus.SUCCESS, data={
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }, message="")
