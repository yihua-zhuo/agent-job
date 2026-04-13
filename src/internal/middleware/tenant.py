"""租户隔离中间件"""
from flask import g, request
from functools import wraps
from .auth import get_current_tenant_id
from ..pkg.errors import AppError, ErrorCode


def require_tenant(f):
    """租户隔离装饰器 - 确保请求属于某个租户"""
    @wraps(f)
    def decorated(*args, **kwargs):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            raise AppError(ErrorCode.UNAUTHORIZED, "缺少租户信息", 401)
        # 将 tenant_id 存入 g 确保在整个请求中可用
        g.tenant_id = tenant_id
        return f(*args, **kwargs)
    return decorated


def tenant_isolation_middleware():
    """租户隔离全局中间件 - 每次请求自动注入 tenant_id 到 g"""
    def middleware():
        # tenant_id 应在 auth 中间件中已提取
        # 此中间件作为保险确保 tenant_id 可用
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id is not None:
            # 确保 tenant_id 是有效整数
            try:
                g.tenant_id = int(tenant_id)
            except (ValueError, TypeError):
                pass  # 保持原值
    
    # 返回中间件函数（Flask 会自动调用）
    return middleware