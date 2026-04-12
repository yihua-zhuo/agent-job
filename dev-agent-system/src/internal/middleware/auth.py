"""认证中间件"""
import os
import jwt
from functools import wraps
from flask import request, g
from typing import Optional, List
from ..pkg.errors import AppError, ErrorCode

# 配置（建议从 config.yaml 加载）
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key')
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
        raise AppError(ErrorCode.UNAUTHORIZED, "Token 已过期", 401)
    except jwt.InvalidTokenError:
        raise AppError(ErrorCode.UNAUTHORIZED, "无效的 Token", 401)


def require_auth(f):
    """JWT 验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token_from_header()
        if not token:
            raise AppError(ErrorCode.UNAUTHORIZED, "缺少认证 Token", 401)

        payload = decode_token(token)
        g.user_id = payload.get("user_id")
        g.tenant_id = payload.get("tenant_id")
        g.roles = payload.get("roles", [])

        return f(*args, **kwargs)
    return decorated


def require_permission(permission: str):
    """权限检查装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if permission not in g.roles:
                raise AppError(ErrorCode.FORBIDDEN, "权限不足", 403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def get_current_tenant_id() -> str:
    """获取当前租户 ID"""
    return getattr(g, "tenant_id", None)
