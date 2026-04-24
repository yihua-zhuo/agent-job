"""多租户隔离中间件"""
from functools import wraps
from typing import Any, Optional
from flask import g

# 假设 AppError 在同级的 errors 模块中定义
from ..pkg.errors.errors import AppError


class TenantMiddleware:
    """多租户隔离中间件 — 使用 flask.g 确保请求级别隔离"""

    def set_tenant_id(self, tenant_id: int):
        """设置当前租户ID（存储在请求上下文而非实例）"""
        g.tenant_id = tenant_id

    def get_tenant_id(self) -> Optional[int]:
        """获取当前租户ID"""
        return getattr(g, 'tenant_id', None)

    def require_tenant(self, f):
        """租户认证装饰器"""
        @wraps(f)
        def decorated(*args, **kwargs):
            if getattr(g, 'tenant_id', None) is None:
                raise AppError(3001, "Tenant not selected")
            return f(*args, **kwargs)
        return decorated

    def filter_by_tenant(self, query, model):
        """为查询自动添加租户过滤"""
        return query.filter(model.tenant_id == g.tenant_id)
