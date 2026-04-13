"""租户隔离中间件"""
from flask import g, request
from functools import wraps
from .auth import get_current_tenant_id


def require_tenant(f):
    """租户隔离装饰器 - 确保请求属于某个租户"""
    @wraps(f)
    def decorated(*args, **kwargs):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            raise Exception("缺少租户信息")
        # 将 tenant_id 存入 g 确保在整个请求中可用
        g.tenant_id = tenant_id
        return f(*args, **kwargs)
    return decorated


def tenant_isolation_middleware():
    """租户隔离全局中间件 - 每次请求自动确保 tenant_id 是 int 类型"""
    def middleware():
        # tenant_id may have been set by the auth decorator as any JSON-serializable type.
        # Coerce it to int here so downstream code gets consistent types.
        raw_tenant_id = getattr(g, 'tenant_id', None)
        if raw_tenant_id is not None:
            try:
                g.tenant_id = int(raw_tenant_id)
            except (ValueError, TypeError):
                # Invalid tenant_id value; leave it as-is so handlers reject it
                pass

    # 返回中间件函数（Flask 会自动调用）
    return middleware
