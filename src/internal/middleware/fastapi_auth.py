"""FastAPI authentication dependency - mirrors Flask auth middleware."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from typing import Optional

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.environ.get('JWT_SECRET_KEY') or os.environ.get('JWT_SECRET') or 'dev-jwt-secret'


def _get_jwt_secret():
    """Read JWT secret with priority: JWT_SECRET_KEY env > app.state.jwt_secret > fallback."""
    env_secret = os.environ.get('JWT_SECRET_KEY') or os.environ.get('JWT_SECRET')
    if env_secret:
        return env_secret
    # app.state.jwt_secret is set by create_app() from settings.jwt_secret
    # This function should be called per-request when the app is fully initialized.
    # For imports that happen before app creation, fall back to env/file-based reading.
    return os.environ.get('JWT_SECRET_KEY') or os.environ.get('JWT_SECRET') or 'dev-jwt-secret'


def get_jwt_secret() -> str:
    """Get current JWT secret per request — reads os.environ at call time."""
    # Priority: JWT_SECRET_KEY env > app.state.jwt_secret (from settings.jwt_secret) > fallback
    env_secret = os.environ.get('JWT_SECRET_KEY')
    if env_secret:
        return env_secret
    try:
        from main import app as _main_app
        secret = getattr(_main_app.state, 'jwt_secret', None)
        if secret:
            return secret
    except Exception:
        pass
    return os.environ.get('JWT_SECRET') or 'dev-jwt-secret'

if os.environ.get('FLASK_ENV') == 'production' and not (os.environ.get('JWT_SECRET_KEY') or os.environ.get('JWT_SECRET')):
    raise ValueError("JWT_SECRET_KEY environment variable is required in production")
JWT_ALGORITHM = "HS256"


class AuthContext:
    """Authenticated user context, replaces Flask `g`."""
    __slots__ = ('user_id', 'tenant_id', 'roles')

    def __init__(self, user_id: int, tenant_id: Optional[int], roles: list):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles


async def get_auth_creds(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Extract bearer token, returns None if absent (allows optional auth)."""
    if credentials is None:
        return None
    return credentials.credentials


async def require_auth(request: Request) -> AuthContext:
    """Decode JWT and populate request.state, mirrors Flask `require_auth` decorator."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证 Token")

    token = auth_header[7:]
    secret = get_jwt_secret()
    print(f"[DEBUG] require_auth token={token[:20]!r}..., secret={secret!r}")
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
        print(f"[DEBUG] payload={payload}")
    except jwt.ExpiredSignatureError:
        print("[DEBUG] ExpiredSignatureError")
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError as e:
        print(f"[DEBUG] InvalidTokenError: {e}")
        raise HTTPException(status_code=401, detail="无效的 Token")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token 缺少 user_id")

    raw_tenant_id = payload.get("tenant_id")
    tenant_id = int(raw_tenant_id) if raw_tenant_id is not None else None

    roles = payload.get("roles", [])

    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)


async def get_current_tenant_id(request: Request) -> int:
    """Extract and validate tenant_id from JWT, raises 401 if missing/invalid."""
    ctx = await require_auth(request)
    if not isinstance(ctx.tenant_id, int) or ctx.tenant_id <= 0:
        raise HTTPException(status_code=401, detail="Token is missing a valid tenant_id")
    return ctx.tenant_id