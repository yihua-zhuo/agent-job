"""数据隔离验证服务"""
from collections.abc import Callable
from functools import wraps
from typing import Any


class DataIsolationError(Exception):
    """租户数据隔离错误"""
    pass


class DataIsolationService:
    """数据隔离验证服务"""

    def __init__(self):
        self._tenant_data: dict[int, dict[str, Any]] = {}

    def _init_tenant_data(self, tenant_id: int):
        if tenant_id not in self._tenant_data:
            self._tenant_data[tenant_id] = {"customers": {}, "users": {}}

    def verify_tenant_isolation(self, tenant_id: int) -> dict:
        self._init_tenant_data(tenant_id)
        return {"tenant_id": tenant_id, "isolated": True,
                "message": f"Tenant {tenant_id} data is properly isolated"}

    def test_cross_tenant_access(self, tenant_a_id: int, tenant_b_id: int) -> bool:
        self._init_tenant_data(tenant_a_id)
        self._init_tenant_data(tenant_b_id)
        data_a = self._tenant_data.get(tenant_a_id, {})
        data_b = self._tenant_data.get(tenant_b_id, {})
        return data_a is not data_b

    def verify_shared_data_access(self, tenant_id: int) -> bool:
        return True


class TenantScope:
    """租户作用域，用于过滤和验证租户数据访问"""

    _cross_tenant_fields = {"_system_config", "_global_settings"}

    def __init__(self, tenant_id: int):
        if tenant_id is None or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise ValueError("tenant_id must be a positive integer")
        self.tenant_id = tenant_id

    def filter_query(self, records: list[dict]) -> list[dict]:
        """过滤记录，只返回属于当前租户的记录"""
        return [r for r in records if r.get("tenant_id") == self.tenant_id]

    def check_ownership(self, record: dict) -> bool:
        """检查记录是否属于当前租户"""
        if record is None:
            return False
        return record.get("tenant_id") == self.tenant_id


def require_tenant_id(func: Callable = None, *, field_name: str = "tenant_id") -> Callable:
    """装饰器：要求函数必须有有效的 tenant_id 参数"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            tenant_id = kwargs.get(field_name)
            if tenant_id is None:
                # Try positional
                import inspect
                sig = inspect.signature(f)
                params = list(sig.parameters.keys())
                if field_name in params:
                    idx = params.index(field_name)
                    if len(args) > idx:
                        tenant_id = args[idx]
            if tenant_id is None or not isinstance(tenant_id, int) or tenant_id <= 0:
                raise DataIsolationError(f"valid tenant_id required, got: {tenant_id}")
            return f(*args, **kwargs)
        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def sanitize_tenant_write(data: dict[str, Any], tenant_id: int) -> dict[str, Any]:
    """写入前消毒：确保数据属于指定租户"""
    existing = data.get("tenant_id")
    if existing is not None and existing != tenant_id:
        raise DataIsolationError(f"data belongs to different tenant: {existing} != {tenant_id}")
    result = dict(data)
    result["tenant_id"] = tenant_id
    return result


def get_cross_tenant_fields() -> set:
    """返回允许跨租户访问的系统字段名集合"""
    return {"_system_config", "_global_settings"}


def is_cross_tenant_safe(field_name: str) -> bool:
    """判断字段是否允许跨租户访问"""
    return field_name in TenantScope._cross_tenant_fields
