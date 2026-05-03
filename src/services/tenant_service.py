"""租户管理服务"""
from typing import Dict, List, Optional, Any
from datetime import datetime


class TenantService:
    """租户管理服务"""

    def __init__(self):
        # 模拟数据存储
        self._tenants: Dict[int, Dict[str, Any]] = {}
        self._counter = 0

    def create_tenant(self, name: str, plan: str, admin_email: str) -> Dict:
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
        return tenant

    def get_tenant(self, tenant_id: int) -> Dict:
        """获取租户详情"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        if tenant.get("deleted_at"):
            raise ValueError(f"Tenant {tenant_id} has been deleted")
        return tenant

    def update_tenant(self, tenant_id: int, **kwargs) -> Dict:
        """更新租户信息"""
        tenant = self.get_tenant(tenant_id)
        allowed_fields = {"name", "plan", "admin_email", "status"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                tenant[key] = value
        tenant["updated_at"] = datetime.utcnow().isoformat()
        return tenant

    def suspend_tenant(self, tenant_id: int):
        """暂停租户"""
        tenant = self.get_tenant(tenant_id)
        tenant["status"] = "suspended"
        tenant["updated_at"] = datetime.utcnow().isoformat()

    def delete_tenant(self, tenant_id: int):
        """删除租户（软删除）"""
        tenant = self.get_tenant(tenant_id)
        tenant["status"] = "deleted"
        tenant["deleted_at"] = datetime.utcnow().isoformat()
        tenant["updated_at"] = tenant["deleted_at"]

    def list_tenants(self, page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict:
        """租户列表"""
        tenants = [t for t in self._tenants.values() if t["status"] != "deleted"]
        if status:
            tenants = [t for t in tenants if t["status"] == status]
        total = len(tenants)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": tenants[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_tenant_usage(self, tenant_id: int) -> Dict:
        """获取租户使用量
        用户数、存储量、API调用量
        """
        tenant = self.get_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "user_count": tenant.get("user_count", 0),
            "storage_used": tenant.get("storage_used", 0),
            "api_calls": tenant.get("api_calls", 0),
        }
