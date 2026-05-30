"""Tenant SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 30


# Hardcoded fixture rows used when state.tenants is empty (i.e. tests that bypass MockState
# seeding). Intentionally static so tests relying on magic IDs like 42 still resolve.
_FIXTURES: dict[int, dict] = {
    1: {
        "id": 1,
        "name": "Tenant A",
        "slug": "tenant-a",
        "plan": "pro",
        "status": "active",
        "settings": {},
        "usage_limits": {},
        "created_at": None,
        "updated_at": None,
    },
    42: {
        "id": 42,
        "name": "Beta Org",
        "slug": "beta-org",
        "plan": "enterprise",
        "status": "active",
        "settings": {"sso": True},
        "usage_limits": {"users": 100},
        "created_at": None,
        "updated_at": None,
    },
}


def make_tenant_handler(state: MockState):
    """Handle all tenant-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into tenants" in sql_text:
            tid = state.tenants_next_id
            state.tenants_next_id += 1
            record = {
                "id": tid,
                "name": params.get("name"),
                "slug": params.get("slug", ""),
                "plan": params.get("plan", "free"),
                "status": params.get("status", "active"),
                "settings": params.get("settings", {}),
                "usage_limits": params.get("usage_limits", {}),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.tenants[tid] = record
            return MockResult([MockRow(record.copy())])

        if "delete" in sql_text and "tenants" in sql_text:
            tenant_id = params.get("id", params.get("tenant_id"))
            # Rule 134: validate ownership before deletion.
            # In multi-tenant SQL, the WHERE clause filters by tenant_id; if both id and
            # requesting_tenant_id are present, confirm the record belongs to the caller.
            requesting_tenant_id = params.get("tenant_id")
            if tenant_id is not None and requesting_tenant_id is not None and tenant_id != requesting_tenant_id:
                # Mismatched: the caller passed an id that does not match their tenant scope
                return MockResult([])
            if tenant_id and tenant_id not in state.tenants:
                return MockResult([])
            if tenant_id in state.tenants:
                del state.tenants[tenant_id]
            return MockResult([[1, "Deleted Tenant", "", "pro", "deleted", {}, {}, None, None]])

        if "update" in sql_text and "tenants" in sql_text:
            tenant_id = params.get("id", params.get("tenant_id"))
            # Rule 134: validate ownership before updates — skip if no tenant context.
            requesting_tenant_id = params.get("tenant_id")
            if tenant_id is not None and requesting_tenant_id is not None and tenant_id != requesting_tenant_id:
                return MockResult([])
            if tenant_id is None or tenant_id not in state.tenants:
                return MockResult([])
            for k, v in params.items():
                if k not in ("id", "tenant_id"):
                    state.tenants[tenant_id][k] = v
            return MockResult([MockRow(state.tenants[tenant_id].copy())])

        if "select" in sql_text and "count" in sql_text and "from tenants" in sql_text:
            return MockResult([[len(state.tenants)]])

        if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text:
            # 'id' bind → direct PK lookup; 'tenant_id' bind → tenant-scoped query.
            # The fallback chain handles both naming conventions without conflating the two
            # operations; a service that passes 'id' intends a PK lookup while one that passes
            # 'tenant_id' intends a tenant-scoped list query (handled separately above).
            tenant_id = params.get("id", params.get("tenant_id"))

            if "limit 1" in sql_text and "where id" in sql_text:
                if tenant_id in state.tenants:
                    return MockResult([MockRow(state.tenants[tenant_id].copy())])
                if tenant_id in _FIXTURES:
                    return MockResult([MockRow(_FIXTURES[tenant_id].copy())])
                return MockResult([])

            if "where id" not in sql_text:
                # tenant-scoped list query: filter by tenant_id param, return empty if absent.
                filter_tenant_id = params.get("tenant_id")
                if filter_tenant_id is not None:
                    matching = [r for rid, r in state.tenants.items() if rid == filter_tenant_id]
                    return MockResult([MockRow(r.copy()) for r in matching])
                return MockResult([])

            if tenant_id in state.tenants:
                return MockResult([MockRow(state.tenants[tenant_id].copy())])
            if tenant_id in _FIXTURES:
                return MockResult([MockRow(_FIXTURES[tenant_id].copy())])
            return MockResult([])

        return None

    return handler


def get_handlers(state: MockState):
    return [make_tenant_handler(state)]


__all__ = ["get_handlers", "make_tenant_handler"]
