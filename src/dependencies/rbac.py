"""Permission-gate FastAPI dependency — @require_permission(resource, action)."""

from collections.abc import Callable

from fastapi import Depends

from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import ForbiddenException
from services.permission_service import has_permission


def require_permission(resource: str, action: str) -> Callable:
    """FastAPI Depends factory — gates an endpoint by resource:action permission.

    Usage:
        @router.get("/", dependencies=[Depends(require_permission("customer", "read"))])
        async def list_customers(ctx: AuthContext = Depends(require_permission("customer", "read"))):
            ...

    The returned callable reads AuthContext via require_auth, then checks
    has_permission for each role in ctx.roles. Raises ForbiddenException
    if no role has the required permission.
    """

    async def guard(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not ctx.roles:
            print(f"[DEBUG] require_permission denied — no roles for user {ctx.user_id}")
            raise ForbiddenException("权限不足")

        target = f"{resource}:{action}"
        for role in ctx.roles:
            if has_permission(role, resource, action):
                return ctx

        print(f"[DEBUG] require_permission denied — user {ctx.user_id} roles={ctx.roles} lacks {target}")
        raise ForbiddenException(f"权限不足: {target}")

    return guard
