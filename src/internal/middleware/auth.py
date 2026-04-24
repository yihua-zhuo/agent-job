"""认证中间件"""
from flask import g, request
from functools import wraps
import jwt
import os
from typing import Optional, List


# 配置（建议从 config.yaml 加载）
JWT_SECRET = os.environ.get('JWT_SECRET') or os.environ.get('JWT_SECRET_KEY') or 'dev-secret'
if not JWT_SECRET:
    if os.environ.get('FLASK_ENV') == 'production':
        raise ValueError("JWT_SECRET environment variable is required in production")
    JWT_SECRET = 'dev-secret'
assert JWT_SECRET is not None
JWT_ALGORITHM = "HS256"


def extract_token_from_header() -> Optional[str]:
    """从请求头提取 Token"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def decode_token(token: str) -> dict:
    """解码 JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token 已过期")
    except jwt.InvalidTokenError:
        raise Exception("无效的 Token")


def require_auth(f):
    """JWT 验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token_from_header()
        if not token:
            raise Exception("缺少认证 Token")

        payload = decode_token(token)
        g.user_id = payload.get("user_id")
        # Ensure tenant_id is stored as an integer
        raw_tenant_id = payload.get("tenant_id")
        if raw_tenant_id is not None:
            g.tenant_id = int(raw_tenant_id)
        else:
            g.tenant_id = None
        g.roles = payload.get("roles", [])

        return f(*args, **kwargs)
    return decorated


def require_permission(permission: str):
    """权限检查装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if permission not in g.roles:
                raise Exception("权限不足")
            return f(*args, **kwargs)
        return decorated
    return decorator


def get_current_tenant_id() -> Optional[int]:
    """获取当前租户 ID"""
    val = getattr(g, "tenant_id", None)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    # Attempt coercion for non-None types (e.g. float from JSON)
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
