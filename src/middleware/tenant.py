"""多租户隔离中间件"""
from functools import wraps

# 假设 AppError 在同级的 errors 模块中定义
try:
    from ..utils.errors import AppError
except ImportError:
    class AppError(Exception):
        def __init__(self, code: int, message: str):
            self.code = code
            self.message = message
            super().__init__(message)


class TenantMiddleware:
    """多租户隔离中间件"""

    def __init__(self):
        self.current_tenant_id: int | None = None

    def set_tenant_id(self, tenant_id: int):
        """设置当前租户ID"""
        self.current_tenant_id = tenant_id

    def get_tenant_id(self) -> int:
        """获取当前租户ID"""
        return self.current_tenant_id

    def require_tenant(self, f):
        """租户认证装饰器"""
        @wraps(f)
        def decorated(*args, **kwargs):
            if not self.current_tenant_id:
                raise AppError(3001, "Tenant not selected")
            return f(*args, **kwargs)
        return decorated

    def filter_by_tenant(self, query, model):
        """为查询自动添加租户过滤"""
        return query.filter(model.tenant_id == self.current_tenant_id)
