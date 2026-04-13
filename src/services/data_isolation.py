"""数据隔离服务 - 提供多租户数据隔离和访问控制工具."""
from typing import Any, Dict, List, Optional, TypeVar, Callable
from functools import wraps


T = TypeVar("T")


class DataIsolationError(Exception):
    """数据隔离相关错误."""
    pass


class TenantScope:
    """租户作用域 - 用于在查询时自动注入租户过滤条件."""

    def __init__(self, tenant_id: int):
        if tenant_id <= 0:
            raise ValueError("tenant_id must be a positive integer")
        self.tenant_id = tenant_id

    def filter_query(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤记录列表，仅返回属于当前租户的记录."""
        return [r for r in records if r.get("tenant_id") == self.tenant_id]

    def check_ownership(self, record: Optional[Dict[str, Any]]) -> bool:
        """检查记录是否属于当前租户."""
        if record is None:
            return False
        return record.get("tenant_id") == self.tenant_id


def require_tenant_id(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器：要求调用时必须传入有效的 tenant_id (大于0)."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tenant_id = kwargs.get("tenant_id")
        if tenant_id is None and args:
            tenant_id = args[0]
        if not isinstance(tenant_id, int) or tenant_id <= 0:
            raise DataIsolationError("A valid tenant_id (positive integer) is required")
        return func(*args, **kwargs)
    return wrapper  # type: ignore[return-value]


def sanitize_tenant_write(data: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
    """在写入数据时注入 tenant_id，防止跨租户数据污染.

    如果数据中已存在 tenant_id 字段且值不同，不允许覆盖。
    这确保了租户隔离在写入层面也能得到保障。
    """
    if "tenant_id" in data and data["tenant_id"] != tenant_id:
        raise DataIsolationError("Attempted to write to a different tenant data")
    return {**data, "tenant_id": tenant_id}


def get_cross_tenant_fields() -> List[str]:
    """返回允许跨租户访问的系统级字段列表."""
    return ["_system_config", "_global_settings"]


def is_cross_tenant_safe(field_name: str) -> bool:
    """判断字段是否允许跨租户访问."""
    return field_name in get_cross_tenant_fields()
