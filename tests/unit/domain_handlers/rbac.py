"""RBAC SQL handlers for unit tests."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime as dt

from tests.unit.conftest import MockResult, MockState

ORDER = 20

# Default roles matching services/rbac_service.py DEFAULT_ROLES
DEFAULT_ROLE_RECORDS = [
    {"id": 1, "tenant_id": 0, "name": "admin",   "display_name": "Administrator",          "description": "Full system access", "is_system": True,  "priority": 100},
    {"id": 2, "tenant_id": 0, "name": "manager",  "display_name": "Manager",                "description": "Manage team",         "is_system": True,  "priority": 80},
    {"id": 3, "tenant_id": 0, "name": "sales",   "display_name": "Sales Representative",  "description": "Manage customers",    "is_system": True,  "priority": 60},
    {"id": 4, "tenant_id": 0, "name": "support", "display_name": "Support Agent",          "description": "Support tasks",       "is_system": True,  "priority": 50},
    {"id": 5, "tenant_id": 0, "name": "viewer",  "display_name": "Viewer",                 "description": "Read-only",           "is_system": True,  "priority": 10},
]

# Default permissions matching services/rbac_service.py DEFAULT_PERMISSIONS
DEFAULT_PERMISSION_RECORDS = [
    {"id": 1,  "name": "customer:create",   "display_name": "Create Customer",    "category": "customer",   "description": ""},
    {"id": 2,  "name": "customer:read",      "display_name": "Read Customer",      "category": "customer",   "description": ""},
    {"id": 3,  "name": "customer:update",    "display_name": "Update Customer",    "category": "customer",   "description": ""},
    {"id": 4,  "name": "customer:delete",    "display_name": "Delete Customer",    "category": "customer",   "description": ""},
    {"id": 5,  "name": "opportunity:create", "display_name": "Create Opportunity", "category": "opportunity","description": ""},
    {"id": 6,  "name": "opportunity:read",    "display_name": "Read Opportunity",   "category": "opportunity","description": ""},
    {"id": 7,  "name": "opportunity:update", "display_name": "Update Opportunity", "category": "opportunity","description": ""},
    {"id": 8,  "name": "opportunity:delete", "display_name": "Delete Opportunity", "category": "opportunity","description": ""},
    {"id": 9,  "name": "ticket:create",      "display_name": "Create Ticket",      "category": "ticket",     "description": ""},
    {"id": 10, "name": "ticket:read",        "display_name": "Read Ticket",        "category": "ticket",     "description": ""},
    {"id": 11, "name": "ticket:update",      "display_name": "Update Ticket",      "category": "ticket",     "description": ""},
    {"id": 12, "name": "ticket:delete",      "display_name": "Delete Ticket",      "category": "ticket",     "description": ""},
    {"id": 13, "name": "user:manage",        "display_name": "Manage Users",       "category": "user",       "description": ""},
    {"id": 14, "name": "user:read",          "display_name": "Read User",          "category": "user",       "description": ""},
    {"id": 15, "name": "admin:all",           "display_name": "Full Admin Access",  "category": "admin",      "description": ""},
]


def _make_role(**kwargs):
    """Build a RoleModel instance with given attrs, using current UTC time."""
    from db.models.rbac import RoleModel
    now = dt.now(UTC)
    return RoleModel(
        id=kwargs.get("id", 0),
        tenant_id=kwargs.get("tenant_id", 0),
        name=kwargs.get("name", ""),
        display_name=kwargs.get("display_name", ""),
        description=kwargs.get("description"),
        is_system=kwargs.get("is_system", False),
        priority=kwargs.get("priority", 0),
        created_at=kwargs.get("created_at", now),
    )


def _make_permission(**kwargs):
    """Build a PermissionModel instance with given attrs."""
    from db.models.rbac import PermissionModel
    now = dt.now(UTC)
    return PermissionModel(
        id=kwargs.get("id", 0),
        name=kwargs.get("name", ""),
        display_name=kwargs.get("display_name", ""),
        category=kwargs.get("category", ""),
        description=kwargs.get("description"),
        created_at=kwargs.get("created_at", now),
    )


def _parse_str_param(params: dict, name: str) -> str | None:
    """Extract a string value for a named param, handling SQLAlchemy _N suffixes."""
    for key, val in params.items():
        if key == name or key.startswith(f"{name}_"):
            return str(val)
    return None


def _parse_int_param(sql_text: str, params: dict, name: str) -> int | None:
    """Extract integer value for named param handling SQLAlchemy's _N suffix.

    SQLAlchemy compiles `limit(N)` to `:limit_1` in bound_params, so check for
    `name_N` keys first, then fall back to bare `name`.
    """
    import re
    # Check params dict for name_N style (SQLAlchemy uses _N suffix for bind params)
    for key, val in params.items():
        if key == name or re.match(rf"^{re.escape(name)}_(\d+)$", key):
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return None


class RBACMockState(MockState):
    def __init__(self):
        super().__init__()
        self.roles: dict[int, dict] = {r["id"]: r.copy() for r in DEFAULT_ROLE_RECORDS}
        self.roles_next_id = 100
        self.permissions: dict[int, dict] = {p["id"]: p.copy() for p in DEFAULT_PERMISSION_RECORDS}
        self.permissions_next_id = 200
        self.role_permissions = []
        self.role_permissions_next_id = 1
        self.user_roles = []
        self.user_roles_next_id = 1


def _build_role_model(record: dict):
    return _make_role(**record)


def _build_permission_model(record: dict):
    return _make_permission(**record)


def make_role_permission_handler(state: RBACMockState):

    def handler(sql_text, params):
        # Insert into role_permissions
        if "insert into role_permissions" in sql_text:
            rid = state.role_permissions_next_id
            state.role_permissions_next_id += 1
            role_id = _parse_int_param(sql_text, params, "role_id")
            permission_id = _parse_int_param(sql_text, params, "permission_id")
            rp = {"id": rid, "role_id": role_id, "permission_id": permission_id}
            state.role_permissions.append(rp)
            return MockResult([rp])

        # Delete from role_permissions
        if "delete from role_permissions" in sql_text:
            role_id = _parse_int_param(sql_text, params, "role_id")
            # role_permissions is cross-tenant via FK to roles (which has tenant isolation),
            # so explicit tenant_id filtering here is not needed.
            state.role_permissions = [rp for rp in state.role_permissions if rp["role_id"] != role_id]
            return MockResult([])

        # Select from role_permissions (join with permissions for list_role_permissions)
        if "select" in sql_text and "from role_permissions" in sql_text:
            role_id = _parse_int_param(sql_text, params, "role_id")
            if role_id is None:
                raise ValueError("role_id could not be determined from query parameters")
            perm_ids = {
                rp["permission_id"]
                for rp in state.role_permissions
                if rp["role_id"] == role_id
            }
            rows = [_build_permission_model(state.permissions[pid]) for pid in perm_ids if pid in state.permissions]
            rows.sort(key=lambda r: (r.category, r.id))
            return MockResult(rows)

        return None

    return handler


def make_role_handler(state: RBACMockState):

    def handler(sql_text, params):
        tenant_id = _parse_int_param(sql_text, params, "tenant_id")

        # Insert into roles
        if "insert into roles" in sql_text:
            rid = state.roles_next_id
            state.roles_next_id += 1
            role = {
                "id": rid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", ""),
                "display_name": params.get("display_name", ""),
                "description": params.get("description"),
                "is_system": params.get("is_system", False),
                "priority": params.get("priority", 0),
                "created_at": dt.now(UTC),
            }
            state.roles[rid] = role
            return MockResult([_build_role_model(role)])

        # Count from roles
        if "select" in sql_text and "count" in sql_text and "from roles" in sql_text:
            rows = [r for r in state.roles.values() if r["tenant_id"] == tenant_id]
            return MockResult([[len(rows)]])

        # Select from roles
        if "select" in sql_text and "from roles" in sql_text:
            rows = [r.copy() for r in state.roles.values()]

            # Determine whether a specific role ID is being queried by inspecting
            # bound params (more robust than SQL-text string matching).
            has_id_param = any(k == "id" or k.startswith("id_") for k in params)

            # WHERE role.id = :id_1 (get_role / update_role / delete_role)
            if has_id_param:
                rid = _parse_int_param(sql_text, params, "id")
                rows = [r for r in rows if r["id"] == rid]
            # Just tenant_id filter (list_roles)
            elif "tenant_id" in sql_text and "offset" in sql_text:
                rows = [r for r in rows if r["tenant_id"] == tenant_id]

            if rows:
                rows.sort(key=lambda r: (-r["priority"], r["id"]))
                # Apply LIMIT/OFFSET (parse directly from SQL text since bound params use _N suffix)
                limit = _parse_int_param(sql_text, params, "limit") or 50
                offset = _parse_int_param(sql_text, params, "offset") or 0
                rows = rows[offset:offset + int(limit)]

            return MockResult([_build_role_model(r) for r in rows])

        # Update roles
        if sql_text.startswith("update") and "roles" in sql_text:
            rid = params.get("id")
            if rid in state.roles:
                for k, v in params.items():
                    if k != "id":
                        state.roles[rid][k] = v
                return MockResult([_build_role_model(state.roles[rid])])
            return MockResult([])

        # Delete from roles
        if sql_text.startswith("delete") and "roles" in sql_text:
            rid = params.get("id")
            if rid in state.roles:
                role = state.roles[rid]
                del state.roles[rid]
                return MockResult([_build_role_model(role)])
            return MockResult([])

        return None

    return handler


def make_permission_handler(state: RBACMockState):

    def handler(sql_text, params):
        # Count from permissions
        if "select" in sql_text and "count" in sql_text and "from permissions" in sql_text:
            rows = [p for p in state.permissions.values()]
            if "where" in sql_text and "category" in sql_text:
                cat = _parse_str_param(params, "category")
                if cat is not None:
                    rows = [r for r in rows if r["category"] == cat]
            return MockResult([[len(rows)]])

        # Select from permissions
        if "select" in sql_text and "from permissions" in sql_text:
            rows = [p.copy() for p in state.permissions.values()]
            if "where" in sql_text and "name" in sql_text and "in" in sql_text:
                # Handle permission_names IN clause: SQLAlchemy binds as name_1, name_2, ...
                names = [str(params[k]) for k in sorted(params) if k == "name" or k.startswith("name_")]
                rows = [r for r in rows if r["name"] in (names or [])]
            elif "where" in sql_text and "category" in sql_text:
                cat = _parse_str_param(params, "category")
                if cat is not None:
                    rows = [r for r in rows if r["category"] == cat]
            rows.sort(key=lambda r: (r["category"], r["id"]))
            if "limit" in sql_text:
                limit = _parse_int_param(sql_text, params, "limit") or 50
                offset = _parse_int_param(sql_text, params, "offset") or 0
                rows = rows[offset:offset + int(limit)]
            return MockResult([_build_permission_model(r) for r in rows])

        return None

    return handler


def make_user_role_handler(state: RBACMockState):

    def _extract_int(sql_text: str, params: dict, suffix: str) -> int | None:
        import re
        for k, v in params.items():
            if k.endswith(suffix):
                return int(v)
        m = re.search(rf":{re.escape(suffix)}_(\d+)", sql_text)
        if m:
            key = f"{suffix}_{m.group(1)}"
            return params.get(key)
        return params.get(suffix)

    def handler(sql_text, params):
        # Insert into user_roles
        if "insert into user_roles" in sql_text:
            urid = state.user_roles_next_id
            state.user_roles_next_id += 1
            ur = {
                "id": urid,
                "user_id": _extract_int(sql_text, params, "user_id"),
                "role_id": _extract_int(sql_text, params, "role_id"),
                "tenant_id": _extract_int(sql_text, params, "tenant_id") or 0,
                "granted_by": _extract_int(sql_text, params, "granted_by") or 0,
                "granted_at": dt.now(UTC),
            }
            state.user_roles.append(ur)
            return MockResult([ur])

        # Delete from user_roles (revoke)
        if "delete from user_roles" in sql_text:
            uid = _extract_int(sql_text, params, "user_id")
            rid = _extract_int(sql_text, params, "role_id")
            tid = _extract_int(sql_text, params, "tenant_id")
            before = len(state.user_roles)
            state.user_roles = [ur for ur in state.user_roles if not (
                ur["user_id"] == uid and ur["role_id"] == rid and ur["tenant_id"] == tid
            )]
            return MockResult([], rowcount=before - len(state.user_roles))

        # Select from user_roles -> return RoleModel objects
        if "select" in sql_text and ("from user_roles" in sql_text or "join user_roles" in sql_text):
            uid = _extract_int(sql_text, params, "user_id")
            tid = _extract_int(sql_text, params, "tenant_id")
            role_ids = [ur["role_id"] for ur in state.user_roles if ur["user_id"] == uid and ur["tenant_id"] == tid]
            rows = [_build_role_model(state.roles[rid]) for rid in role_ids if rid in state.roles]
            rows.sort(key=lambda r: -r.priority)
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: RBACMockState):
    return [
        make_role_handler(state),
        make_permission_handler(state),
        make_role_permission_handler(state),
        make_user_role_handler(state),
    ]


__all__ = ["get_handlers", "RBACMockState"]
