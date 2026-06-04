"""Static, in-memory permission service — glob-aware, no DB required."""

from fnmatch import fnmatch

from services.rbac_service import DEFAULT_PERMISSIONS

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": ["*"],
    "admin": [p[0] for p in DEFAULT_PERMISSIONS],
    "manager": [
        "customer:read",
        "customer:update",
        "opportunity:read",
        "opportunity:create",
        "opportunity:update",
        "ticket:read",
        "ticket:create",
        "ticket:update",
        "user:read",
    ],
    "sales": [
        "customer:read",
        "customer:create",
        "customer:update",
        "opportunity:read",
        "opportunity:create",
        "opportunity:update",
    ],
    "support": [
        "customer:read",
        "opportunity:read",
        "ticket:read",
        "ticket:create",
        "ticket:update",
        "ticket:*",
    ],
    "viewer": [
        "customer:read",
        "opportunity:read",
        "ticket:read",
    ],
    "member": [
        "customer:read",
        "customer:create",
        "opportunity:read",
    ],
}


def has_permission(role: str, resource: str, action: str) -> bool:
    """Check if a role grants permission for a resource:action pair.

    Matching order:
    1. Unknown role → False (no KeyError)
    2. Exact "resource:action" match
    3. Global wildcard "*" in role permissions
    4. Resource-level wildcard "<resource>:*" in role permissions
    5. fnmatch on "<resource>:*" patterns (catches other glob forms)
    """
    perms = ROLE_PERMISSIONS.get(role, [])
    if not perms:
        return False

    target = f"{resource}:{action}"

    # Exact match
    if target in perms:
        return True

    # Super-admin wildcard
    if "*" in perms:
        return True

    # Resource-level wildcard (direct check)
    resource_wildcard = f"{resource}:*"
    if resource_wildcard in perms:
        return True

    # fnmatch fallback for glob patterns like "customer:*" / "*:read"
    for perm in perms:
        if "*" in perm and fnmatch(target, perm):
            return True

    return False


def check_permission(user_id: int, tenant_id: int, resource: str, action: str) -> bool:
    """Static stub — no DB session available, always returns False.

    A future DB-backed version will look up user roles from the database.
    """
    return False
