"""Tenant SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 30


def tenant_handler(sql_text, params):
    """Handle all tenant-related SQL."""
    if "insert into tenants" in sql_text:
        return MockResult([MockRow({"id": 1, "name": params.get("name"), "plan": params.get("plan"), "status": "active", "settings": params.get("settings", "{}"), "created_at": params.get("now"), "updated_at": params.get("now")})])

    if "delete" in sql_text and "tenants" in sql_text:
        tenant_id = params.get("tenant_id")
        if tenant_id and tenant_id != 1:
            return MockResult([])
        return MockResult([[1, "Deleted Tenant", "pro", "deleted", "{}", None, None]])

    if "update" in sql_text and "tenants" in sql_text:
        tenant_id = params.get("tenant_id") or params.get("id")
        if tenant_id == 1:
            return MockResult([[1, "Updated Name", "pro", "active", "{}", None, None]])
        return MockResult([])

    if "select" in sql_text and "count" in sql_text and "from tenants" in sql_text:
        return MockResult([[2]])

    if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text:
        tenant_id = params.get("tenant_id")
        if "limit 1" in sql_text and "where id" in sql_text:
            if tenant_id == 1:
                return MockResult([MockRow({"id": 1})])
            if tenant_id == 42:
                return MockResult([MockRow({"id": 42, "name": "Beta Org", "plan": "enterprise", "status": "active", "settings": '{"sso": true}', "created_at": None, "updated_at": None})])
            return MockResult([])

        if "where id" not in sql_text:
            return MockResult([
                MockRow({"id": 1, "name": "Tenant A", "plan": "pro", "status": "active", "settings": "{}", "created_at": None, "updated_at": None}),
                MockRow({"id": 2, "name": "Tenant B", "plan": "enterprise", "status": "active", "settings": "{}", "created_at": None, "updated_at": None}),
            ])

        if tenant_id == 42:
            return MockResult([MockRow({"id": 42, "name": "Beta Org", "plan": "enterprise", "status": "active", "settings": '{"sso": true}', "created_at": None, "updated_at": None})])
        return MockResult([])

    return None


def get_handlers(state: MockState):
    return [tenant_handler]


__all__ = ["get_handlers", "tenant_handler"]
