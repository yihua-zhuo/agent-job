"""Opportunity Activity SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 41


def param(params, name, default=None):
    if name in params:
        return params[name]
    prefix = f"{name}_"
    for key, value in params.items():
        if key.startswith(prefix):
            return value
    return default


def make_opportunity_activity_handler(state: MockState):
    """Handle INSERT and SELECT on opportunity_activities."""

    def handler(sql_text, params):
        if "insert into opportunity_activities" in sql_text:
            aid = state.activities_next_id
            state.activities_next_id += 1
            record = {
                "id": aid,
                "tenant_id": params.get("tenant_id", 0),
                "opportunity_id": params.get("opportunity_id", 0),
                "event_type": params.get("event_type", ""),
                "event_timestamp": params.get("event_timestamp"),
                "metadata": params.get("event_metadata", {}),
            }
            state.activities[aid] = record
            return MockResult([MockRow(record.copy())])

        if "from opportunity_activities" not in sql_text:
            return None

        # SELECT — find by id or list all for tenant
        activity_id = param(params, "id")
        if "where" in sql_text and "opportunity_activities.id" in sql_text and activity_id is not None:
            tenant_id = param(params, "tenant_id")
            if activity_id in state.activities:
                rec = state.activities[activity_id].copy()
                if tenant_id is not None and rec.get("tenant_id") != tenant_id:
                    return MockResult([])
                return MockResult([MockRow(rec)])
            return MockResult([])

        # List all for tenant
        tenant_id = param(params, "tenant_id", 0)
        limit = params.get("limit") or params.get("param_1")
        offset = params.get("offset") or params.get("param_2", 0)
        filtered = [MockRow(r.copy()) for r in state.activities.values() if r.get("tenant_id") == tenant_id]
        rows = filtered[int(offset) : int(offset) + int(limit)] if limit else filtered[int(offset) :]
        return MockResult(rows)

    return handler


def get_handlers(state: MockState):
    return [make_opportunity_activity_handler(state)]


__all__ = ["get_handlers", "make_opportunity_activity_handler"]
