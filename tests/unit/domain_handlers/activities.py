"""Activity SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 70


def param(params, name, default=None):
    if name in params:
        return params[name]
    prefix = f"{name}_"
    for key, value in params.items():
        if key.startswith(prefix):
            return value
    return default


def matches_filters(record, tenant_id=None, customer_id=None, activity_type=None):
    if tenant_id is not None and record.get("tenant_id") != tenant_id:
        return False
    if customer_id is not None and record.get("customer_id") != customer_id:
        return False
    if activity_type is not None and record.get("type") != activity_type:
        return False
    return True


def make_activity_handler(state: MockState):
    """Handle all activity-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into activities" in sql_text:
            aid = state.activities_next_id
            state.activities_next_id += 1
            record = {
                "id": aid,
                "tenant_id": params.get("tenant_id", 0),
                "customer_id": params.get("customer_id", 0),
                "opportunity_id": params.get("opportunity_id"),
                "type": params.get("type", "call"),
                "content": params.get("content", ""),
                "created_by": params.get("created_by", 0),
                "created_at": params.get("created_at"),
            }
            state.activities[aid] = record
            return MockResult([MockRow(record.copy())])

        is_activity_query = (
            "from activities" in sql_text
            or (sql_text.startswith("update") and "activities" in sql_text)
            or (sql_text.startswith("delete") and "activities" in sql_text)
        )
        if not is_activity_query:
            return None

        if sql_text.startswith("update") and "activities" in sql_text:
            activity_id = param(params, "id")
            tenant_id = param(params, "tenant_id")
            if activity_id in state.activities:
                rec = state.activities[activity_id]
                if tenant_id is not None and rec.get("tenant_id") != tenant_id:
                    return MockResult([])
                for k, v in params.items():
                    if k not in ("id", "tenant_id") and not k.startswith(("id_", "tenant_id_")):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if sql_text.startswith("delete") and "activities" in sql_text:
            activity_id = param(params, "id")
            tenant_id = param(params, "tenant_id")
            if activity_id in state.activities and matches_filters(state.activities[activity_id], tenant_id=tenant_id):
                state.activities.pop(activity_id)
                return MockResult([MockRow({"id": activity_id})])
            return MockResult([])

        if "select" in sql_text and "count" in sql_text and "from activities" in sql_text:
            tenant_id = param(params, "tenant_id")
            customer_id = param(params, "customer_id")
            activity_type = param(params, "type")
            count_val = len(
                [
                    r
                    for r in state.activities.values()
                    if matches_filters(r, tenant_id=tenant_id, customer_id=customer_id, activity_type=activity_type)
                ]
            )
            return MockResult([[count_val]])

        activity_id = param(params, "id")
        if "where" in sql_text and "activities.id" in sql_text and activity_id is not None:
            tenant_id = param(params, "tenant_id")
            if activity_id in state.activities and matches_filters(state.activities[activity_id], tenant_id=tenant_id):
                return MockResult([MockRow(state.activities[activity_id].copy())])
            return MockResult([])

        if state.activities:
            tenant_id = param(params, "tenant_id", 0)
            customer_id = param(params, "customer_id")
            activity_type = param(params, "type")
            rows = [
                MockRow(r.copy())
                for r in state.activities.values()
                if matches_filters(r, tenant_id=tenant_id, customer_id=customer_id, activity_type=activity_type)
            ]
            return MockResult(rows)

        return MockResult([])

    return handler


def get_handlers(state: MockState):
    return [make_activity_handler(state)]


__all__ = ["get_handlers", "make_activity_handler"]
