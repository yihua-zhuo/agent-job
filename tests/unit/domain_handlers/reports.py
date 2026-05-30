"""Report SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def _get_tenant_id(sql_text, params):
    """Extract tenant_id from bound params, handling SQLAlchemy's name mangling.

    SQLAlchemy appends a numeric suffix when a param name appears multiple
    times in a query (e.g. tenant_id_1, tenant_id_2). We strip a trailing
    numeric suffix only when it forms a contiguous numeric segment after an
    underscore, so e.g. user_id → user_i is no longer incorrectly stripped.
    """
    for key, val in params.items():
        if "_" in key:
            prefix, suffix = key.rsplit("_", 1)
            if suffix.isdigit():
                stripped = prefix
            else:
                continue
        else:
            stripped = key.rstrip("0123456789")
        if stripped == "tenant_id":
            return val
    return params.get("tenant_id", 0)


def _get_report_id(params):
    """Extract the report id from params, handling SQLAlchemy's name mangling.

    SQLAlchemy renames duplicate param occurrences (e.g. `id` → `id_1`) when
    the same column appears multiple times in a compiled statement.
    Handles both bare `id` and `report_id` bound parameters.
    """
    if "id" in params:
        return params["id"]
    if "report_id" in params:
        return params["report_id"]
    for key, val in params.items():
        if key.startswith("id_") and isinstance(val, int):
            return val
    return None


def make_report_handler(state: MockState):
    """Handle all report-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""
    # Domain-owned state stored via the opaque slot so conftest.py stays agnostic.
    if "reports" not in state.opaque:
        state.opaque["reports"] = {"records": {}, "next_id": 1}
    _reports = state.opaque["reports"]

    def handler(sql_text, params):
        if "insert into reports" in sql_text:
            _get_tenant_id(sql_text, params)
            rid = _reports["next_id"]
            _reports["next_id"] += 1
            record = {
                "id": rid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Test Report"),
                "type": params.get("type", "custom"),
                "config": params.get("config", {}),
                "date_range": params.get("date_range", {}),
                "created_by": params.get("created_by", 0),
                "last_run_at": params.get("last_run_at"),
                "created_at": params.get("created_at"),
            }
            _reports["records"][rid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "reports" in sql_text:
            report_id = _get_report_id(params)
            rec = _reports["records"].get(report_id)
            if rec is None or rec.get("tenant_id") != _get_tenant_id(sql_text, params):
                return MockResult([])
            for k, v in params.items():
                if k not in ("id", "tenant_id"):
                    rec[k] = v
            return MockResult([MockRow(rec.copy())])

        if sql_text.startswith("delete") and "reports" in sql_text:
            report_id = _get_report_id(params)
            rec = _reports["records"].get(report_id)
            if rec is None or rec.get("tenant_id") != _get_tenant_id(sql_text, params):
                return MockResult([])
            del _reports["records"][report_id]
            return MockResult([MockRow({"id": report_id})])

        if sql_text.startswith("select") and "count(" in sql_text and "from reports" in sql_text:
            tenant_id = _get_tenant_id(sql_text, params)
            count_val = sum(1 for r in _reports["records"].values() if r.get("tenant_id") == tenant_id)
            return MockResult([count_val])

        # Require both 'where reports.id' and 'tenant_id' to reduce false positives.
        if "where reports.id" in sql_text and "tenant_id" in sql_text:
            report_id = _get_report_id(params)
            rec = _reports["records"].get(report_id)
            if rec is not None and rec.get("tenant_id") == _get_tenant_id(sql_text, params):
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        # All other SELECT from reports (list with or without ORDER BY).
        if "select" in sql_text and "from reports" in sql_text:
            tenant_id = _get_tenant_id(sql_text, params)
            rows = [MockRow(rec.copy()) for rec in _reports["records"].values() if rec.get("tenant_id") == tenant_id]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_report_handler(state)]


__all__ = ["get_handlers", "make_report_handler"]
