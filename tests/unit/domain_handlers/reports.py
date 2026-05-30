"""Report SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_report_handler(state: MockState):
    """Handle all report-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""
    if not hasattr(state, "report_records"):
        state.report_records: dict[int, dict] = {}
    if not hasattr(state, "report_records_next_id"):
        state.report_records_next_id: int = 1
    def handler(sql_text, params):
        if "insert into reports" in sql_text:
            rid = state.report_records_next_id
            state.report_records_next_id += 1
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
            state.report_records[rid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "reports" in sql_text:
            report_id = params.get("id")
            rec = state.report_records.get(report_id)
            if rec is not None and rec.get("tenant_id") == (params.get("tenant_id") or 0):
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if sql_text.startswith("delete") and "reports" in sql_text:
            report_id = params.get("id")
            rec = state.report_records.get(report_id)
            if rec is not None and rec.get("tenant_id") == (params.get("tenant_id") or 0):
                del state.report_records[report_id]
                return MockResult([MockRow({"id": report_id})])
            return MockResult([])

        if "select" in sql_text and "count" in sql_text and "from reports" in sql_text:
            tenant_id = params.get("tenant_id", 0)
            count_val = sum(1 for r in state.report_records.values() if r.get("tenant_id") == tenant_id)
            return MockResult([[count_val]])

        if "from reports where id" in sql_text and "tenant_id" in sql_text:
            report_id = params.get("id")
            rec = state.report_records.get(report_id)
            if rec is not None and rec.get("tenant_id") == params.get("tenant_id"):
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if "select" in sql_text and "from reports" in sql_text and "order by" in sql_text:
            tenant_id = params.get("tenant_id", 0)
            rows = [MockRow(rec.copy()) for rec in state.report_records.values() if rec.get("tenant_id") == tenant_id]
            return MockResult(rows)

        if "select" in sql_text and "from reports" in sql_text and "order by" not in sql_text:
            tenant_id = params.get("tenant_id", 0)
            rows = [MockRow(rec.copy()) for rec in state.report_records.values() if rec.get("tenant_id") == tenant_id]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_report_handler(state)]


__all__ = ["get_handlers", "make_report_handler"]
