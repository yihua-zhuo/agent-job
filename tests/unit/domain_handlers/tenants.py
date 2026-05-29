"""Tenant SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 30


_FIXTURES: dict[int, dict] = {
    1: {
        "id": 1,
        "name": "Tenant A",
        "slug": "tenant-a",
        "plan": "pro",
        "status": "active",
        "settings": "{}",
        "usage_limits": "{}",
        "created_at": None,
        "updated_at": None,
    },
    42: {
        "id": 42,
        "name": "Beta Org",
        "slug": "beta-org",
        "plan": "enterprise",
        "status": "active",
        "settings": '{"sso": true}',
        "usage_limits": '{"users": 100}',
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
                "settings": params.get("settings", "{}"),
                "usage_limits": params.get("usage_limits", "{}"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.tenants[tid] = record
            return MockResult([MockRow(record.copy())])

        if "delete" in sql_text and "tenants" in sql_text:
            tenant_id = params.get("id", params.get("tenant_id"))
            if tenant_id and tenant_id not in state.tenants:
                return MockResult([])
            if tenant_id in state.tenants:
                del state.tenants[tenant_id]
            return MockResult([[1, "Deleted Tenant", "", "pro", "deleted", "{}", "{}", None, None]])

        if "update" in sql_text and "tenants" in sql_text:
            tenant_id = params.get("id", params.get("tenant_id"))
            if tenant_id in state.tenants:
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        state.tenants[tenant_id][k] = v
                return MockResult([MockRow(state.tenants[tenant_id].copy())])
            return MockResult(
                [[1, "Updated Name", "updated-slug", "pro", "active", "{}", "{}", None, None]]
            )

        if "select" in sql_text and "count" in sql_text and "from tenants" in sql_text:
            return MockResult([[len(state.tenants) or 2]])

        if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text:
            tenant_id = params.get("id", params.get("tenant_id"))

            if "limit 1" in sql_text and "where id" in sql_text:
                if tenant_id in state.tenants:
                    return MockResult([MockRow(state.tenants[tenant_id].copy())])
                if tenant_id in _FIXTURES:
                    return MockResult([MockRow(_FIXTURES[tenant_id].copy())])
                return MockResult([])

            if "where id" not in sql_text:
                if state.tenants:
                    rows = [MockRow(r.copy()) for r in state.tenants.values()]
                else:
                    rows = [
                        MockRow(_FIXTURES[1].copy()),
                        MockRow(
                            {
                                "id": 2,
                                "name": "Tenant B",
                                "slug": "tenant-b",
                                "plan": "enterprise",
                                "status": "active",
                                "settings": "{}",
                                "usage_limits": "{}",
                                "created_at": None,
                                "updated_at": None,
                            }
                        ),
                    ]
                return MockResult(rows)

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
