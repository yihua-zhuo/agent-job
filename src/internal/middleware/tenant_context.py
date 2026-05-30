"""Thread-safe tenant ID storage using contextvars.

Unlike threading.local, ContextVar correctly propagates across
asyncio tasks within the same request context.
"""

from contextvars import ContextVar

from pkg.errors.app_exceptions import UnauthorizedException

_tenant_id_var: ContextVar[int | None] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: int) -> None:
    """Store the current tenant_id in the request context."""
    _tenant_id_var.set(tenant_id)


def get_tenant_id() -> int | None:
    """Retrieve the current tenant_id from the request context.

    Returns None if no tenant context has been set.
    """
    return _tenant_id_var.get()


def require_tenant_id() -> int:
    """Retrieve the current tenant_id, raising if unset.

    Raises:
        UnauthorizedException: If no tenant context has been set.
    """
    tid = _tenant_id_var.get()
    if tid is None:
        raise UnauthorizedException("Tenant context is not set")
    return tid


def clear() -> None:
    """Clear the tenant context.

    Call this at the end of a request to prevent tenant_id leaking
    into subsequent requests processed by the same worker.
    """
    _tenant_id_var.set(None)
