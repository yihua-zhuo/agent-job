"""Auth/permission dependency guards — requirement 11.

Usage:
    @router.delete("/{user_id}", dependencies=[Depends(require_role("admin"))])
    async def delete_user(...):
        ...

    # All roles:
    @router.get("/", dependencies=[Depends(require_role("admin", "editor"))])
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from typing import Optional, Callable

from internal.middleware.fastapi_auth import AuthContext

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.environ.get('JWT_SECRET') or os.environ.get('JWT_SECRET_KEY') or 'dev-secret'
if os.environ.get('FLASK_ENV') == 'production' and not os.environ.get('JWT_SECRET'):
    raise ValueError("JWT_SECRET environment variable is required in production")
JWT_ALGORITHM = "HS256"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthContext:
    """Decode JWT and return AuthContext. Raises 401 if missing/invalid."""
    if not credentials:
        raise HTTPException(status_code=401, detail="缺少认证 Token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token 缺少 user_id")

    raw_tenant_id = payload.get("tenant_id")
    tenant_id = int(raw_tenant_id) if raw_tenant_id is not None else None
    roles = payload.get("roles", [])

    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)


def require_role(*allowed_roles: str) -> Callable:
    """Permission guard — returns a FastAPI Depends that checks user role.

    Usage:
        @router.delete("/{user_id}", dependencies=[Depends(require_role("admin"))])
        async def delete_user(current_user: AuthContext = Depends(get_current_user)):
            ...
    """
    def guard(current_user: AuthContext = Depends(get_current_user)) -> AuthContext:
        user_roles = set(current_user.roles) if current_user.roles else set()
        allowed = set(allowed_roles)
        if not user_roles.intersection(allowed):
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user

    return guard


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[AuthContext]:
    """Optional auth — returns None if no bearer token provided."""
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

    user_id = payload.get("user_id")
    if user_id is None:
        return None

    raw_tenant_id = payload.get("tenant_id")
    tenant_id = int(raw_tenant_id) if raw_tenant_id is not None else None
    roles = payload.get("roles", [])

    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)