"""租户管理服务"""
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.models.response import ApiResponse, PaginatedData


class TenantService:
    """租户管理服务"""

    def __init__(self):
        # 模拟数据存储
        self._tenants: Dict[int, Dict[str, Any]] = {}
        self._counter = 0

    def create_tenant(self, name: str, plan: str, admin_email: str) -> ApiResponse[Dict]:
        """创建租户（公司）"""
        self._counter += 1
        tenant_id = self._counter
        now = datetime.utcnow().isoformat()
        tenant = {
            "id": tenant_id,
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
        self._tenants[tenant_id] = tenant
        return ApiResponse.success(data=tenant, message='租户创建成功')

    def get_tenant(self, tenant_id: int) -> ApiResponse[Dict]:
        """获取租户详情"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return ApiResponse.error(message=f'Tenant {tenant_id} not found', code=1404)
        if tenant.get("deleted_at"):
            return ApiResponse.error(message=f'Tenant {tenant_id} has been deleted', code=1404)
        return ApiResponse.success(data=tenant)

    def update_tenant(self, tenant_id: int, **kwargs) -> ApiResponse[Dict]:
        """更新租户信息"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return ApiResponse.error(message=f'Tenant {tenant_id} not found', code=1404)
        if tenant.get("deleted_at"):
            return ApiResponse.error(message=f'Tenant {tenant_id} has been deleted', code=1404)
        
        allowed_fields = {"name", "plan", "admin_email", "status"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                tenant[key] = value
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return ApiResponse.success(data=tenant, message='租户信息更新成功')

    def suspend_tenant(self, tenant_id: int) -> ApiResponse[Dict]:
        """暂停租户"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return ApiResponse.error(message=f'Tenant {tenant_id} not found', code=1404)
        if tenant.get("deleted_at"):
            return ApiResponse.error(message=f'Tenant {tenant_id} has been deleted', code=1404)
        
        tenant["status"] = "suspended"
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return ApiResponse.success(data={'tenant_id': tenant_id, 'status': 'suspended'}, message='租户已暂停')

    def delete_tenant(self, tenant_id: int) -> ApiResponse[Dict]:
        """删除租户（软删除）"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return ApiResponse.error(message=f'Tenant {tenant_id} not found', code=1404)
        if tenant.get("deleted_at"):
            return ApiResponse.error(message=f'Tenant {tenant_id} has been deleted', code=1404)
        
        tenant["status"] = "deleted"
        tenant["deleted_at"] = datetime.utcnow().isoformat()
        tenant["updated_at"] = tenant["deleted_at"]
        return ApiResponse.success(data={'tenant_id': tenant_id}, message='租户已删除')

    def list_tenants(self, page: int = 1, page_size: int = 20, status: Optional[str] = None) -> ApiResponse[PaginatedData[Dict]]:
        """租户列表"""
        tenants = [t for t in self._tenants.values() if t["status"] != "deleted"]
        if status:
            tenants = [t for t in tenants if t["status"] == status]
        
        total = len(tenants)
        start = (page - 1) * page_size
        end = start + page_size
        items = tenants[start:end]
        
        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message='查询成功'
        )

    def get_tenant_usage(self, tenant_id: int) -> ApiResponse[Dict]:
        """获取租户使用量 - 用户数、存储量、API调用量"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return ApiResponse.error(message=f'Tenant {tenant_id} not found', code=1404)
        if tenant.get("deleted_at"):
            return ApiResponse.error(message=f'Tenant {tenant_id} has been deleted', code=1404)
        
        usage = {
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }
        return ApiResponse.success(data=usage)
