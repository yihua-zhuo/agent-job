"""Opportunity Activity SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 41  # Placed after sales (ORDER=40) to avoid accidental handler overlap


def make_opportunity_activity_handler(state: MockState):
    """Handle INSERT, SELECT, UPDATE, and DELETE on opportunity_activities."""

    if not hasattr(state, "opportunity_activities"):
        state.opportunity_activities = {}
    if not hasattr(state, "opportunity_activities_next_id"):
        state.opportunity_activities_next_id = 1

    def handler(sql_text, params):
        if "insert into opportunity_activities" in sql_text:
            aid = state.opportunity_activities_next_id
            state.opportunity_activities_next_id += 1
            record = {
                "id": aid,
                "tenant_id": params.get("tenant_id", 0),
                "opportunity_id": params.get("opportunity_id", 0),
                "event_type": params.get("event_type", ""),
                "event_timestamp": params.get("event_timestamp"),
                "event_metadata": params.get("event_metadata", {}),
            }
            state.opportunity_activities[aid] = record
            return MockResult([MockRow(record.copy())])

        if "opportunity_activities" not in sql_text:
            return MockResult([])

        # SELECT — find by id or list all for tenant
        activity_id = params.get("id")
        if "where" in sql_text and "opportunity_activities.id" in sql_text and activity_id is not None:
            tenant_id = params.get("tenant_id")
            if activity_id in state.opportunity_activities:
                rec = state.opportunity_activities[activity_id].copy()
                if tenant_id is not None and rec.get("tenant_id") != tenant_id:
                    return MockResult([])
                return MockResult([MockRow(rec)])
            return MockResult([])

        # UPDATE
        if "update opportunity_activities" in sql_text:
            aid = params.get("id")
            if aid in state.opportunity_activities:
                tenant_id = params.get("tenant_id")
                rec = state.opportunity_activities[aid]
                if tenant_id is not None and rec.get("tenant_id") != tenant_id:
                    return MockResult([])
                for key in ("event_type", "event_metadata", "event_timestamp"):
                    if key in params:
                        rec[key] = params[key]
                return MockResult([])
            return MockResult([])

        # DELETE
        if "delete from opportunity_activities" in sql_text:
            aid = params.get("id")
            if aid in state.opportunity_activities:
                tenant_id = params.get("tenant_id")
                if tenant_id is not None and state.opportunity_activities[aid].get("tenant_id") != tenant_id:
                    return MockResult([])
                del state.opportunity_activities[aid]
                return MockResult([])
            return MockResult([])

        # List all for tenant
        tenant_id = params.get("tenant_id", 0)
        limit = params.get("limit") or params.get("param_1")
        offset = params.get("offset") or params.get("param_2", 0)
        filtered = [
            MockRow(r.copy())
            for r in state.opportunity_activities.values()
            if r.get("tenant_id") == tenant_id
        ]
        if limit is not None:
            rows = filtered[int(offset) : int(offset) + int(limit)]
        else:
            rows = filtered[int(offset) :]
        return MockResult(rows)

    return handler


def get_handlers(state: MockState):
    return [make_opportunity_activity_handler(state)]


__all__ = ["get_handlers", "make_opportunity_activity_handler"]
