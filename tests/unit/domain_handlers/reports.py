"""Report SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


class _MissingTenantIdError(Exception):
    """Raised when tenant_id cannot be extracted from bound params."""

    pass


def _get_tenant_id(params):
    """Extract tenant_id from bound params, handling SQLAlchemy's name mangling.

    SQLAlchemy appends a numeric suffix when a param name appears multiple
    times in a query (e.g. tenant_id_1, tenant_id_2). We only strip the
    suffix when the key contains an underscore and the suffix is purely
    numeric — avoiding corruption of keys like created_by.

    Raises _MissingTenantIdError if tenant_id is absent, so that UPDATE/DELETE
    handlers return MockResult([]) instead of silently operating on tenant_id=0.
    """
    for key, val in params.items():
        if "_" in key:
            prefix, suffix = key.rsplit("_", 1)
            if suffix.isdigit():
                if prefix == "tenant_id":
                    return val
        elif key == "tenant_id":
            return val
    raise _MissingTenantIdError(
        f"tenant_id not found in bound params (keys: {list(params.keys())}). "
        "Ensure every SQL query includes a tenant_id bind parameter."
    )


# Sentinel used by _get_report_id when no report id param is found.
_REPORT_ID_NOT_FOUND = -1


def _get_report_id(params):
    """Extract the report id from params, handling SQLAlchemy's name mangling.

    SQLAlchemy renames duplicate param occurrences (e.g. `id` → `id_1`) when
    the same column appears multiple times in a compiled statement.
    Handles both bare `id` and `report_id` bound parameters.

    Returns _REPORT_ID_NOT_FOUND (-1) when no id param is present, so that
    UPDATE/DELETE handlers return MockResult([]) instead of silently matching
    record id=0 or None.
    """
    if "id" in params:
        return params["id"]
    if "report_id" in params:
        return params["report_id"]
    for key, val in params.items():
        if key.startswith("id_") and isinstance(val, int):
            return val
    return _REPORT_ID_NOT_FOUND


def _get_schedule_id(params):
    """Extract the schedule (report_schedules.id) from params, handling SQLAlchemy's name mangling."""
    if "id" in params:
        return params["id"]
    for key, val in params.items():
        if key.startswith("id_") and isinstance(val, int):
            return val
    return None


def _get_mangled(params, base: str):
    """Return the first value in params whose key equals base or base_<number>.

    Used to retrieve SQLAlchemy-mangled params (e.g. updated_at_1) without
    requiring callers to know the suffix in advance.
    """
    if base in params:
        return params[base]
    for key, val in params.items():
        if key.startswith(base + "_") and key[len(base) + 1:].isdigit():
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
            if report_id == _REPORT_ID_NOT_FOUND:
                return MockResult([])
            try:
                tenant_id_val = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            assert isinstance(tenant_id_val, int)
            rec = _reports["records"].get(report_id)
            if rec is None or rec.get("tenant_id") != tenant_id_val:
                return MockResult([])
            return MockResult([MockRow(rec.copy())])

        if sql_text.startswith("delete") and "reports" in sql_text:
            report_id = _get_report_id(params)
            if report_id == _REPORT_ID_NOT_FOUND:
                return MockResult([])
            try:
                tenant_id_val = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            rec = _reports["records"].get(report_id)
            if rec is None or rec.get("tenant_id") != tenant_id_val:
                return MockResult([])
            del _reports["records"][report_id]
            return MockResult([MockRow({"id": report_id})])

        if sql_text.startswith("select") and "count(" in sql_text and "from reports" in sql_text:
            tenant_id = _get_tenant_id(params)
            # Inspect sql_text for filter predicates so counts reflect actual query filters.
            recs = _reports["records"].values()
            recs = (r for r in recs if r.get("tenant_id") == tenant_id)
            if '"type"' in sql_text or "'type'" in sql_text:
                type_val = params.get("type") or _get_mangled(params, "type")
                if type_val is not None:
                    recs = (r for r in recs if r.get("type") == type_val)
            count_val = sum(1 for r in recs)
            return MockResult([count_val])

        # Require both 'where reports.id' and 'tenant_id' to reduce false positives.
        if "where reports.id" in sql_text and "tenant_id" in sql_text:
            report_id = _get_report_id(params)
            if report_id == _REPORT_ID_NOT_FOUND:
                return MockResult([])
            try:
                tenant_id_val = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            rec = _reports["records"].get(report_id)
            if rec is not None and rec.get("tenant_id") == tenant_id_val:
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        # All other SELECT from reports (list with or without ORDER BY).
        if "select" in sql_text and "from reports" in sql_text:
            try:
                tenant_id_val = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            # Apply LIMIT page_size (default 20) to mirror real DB pagination
            # and mask pagination bugs in the service layer.
            page_size = params.get("page_size", 20)
            rows = [
                MockRow(rec.copy())
                for rec in _reports["records"].values()
                if rec.get("tenant_id") == tenant_id_val
            ][:page_size]
            return MockResult(rows)

        return None

    return handler


def make_schedule_handler(state: MockState):
    """Handle INSERT/SELECT/UPDATE/DELETE on report_schedules (schedule_report upserts)."""
    if "report_schedules" not in state.opaque:
        state.opaque["report_schedules"] = {"records": {}, "next_id": 1}
    _schedules = state.opaque["report_schedules"]

    def handler(sql_text, params):
        # INSERT: upsert a schedule record keyed on (tenant_id, report_id).
        if "insert into report_schedules" in sql_text:
            try:
                tenant_id = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            report_id = _get_mangled(params, "report_id")
            existing = next(
                (
                    rec
                    for rec in _schedules["records"].values()
                    if rec.get("tenant_id") == tenant_id and rec.get("report_id") == report_id
                ),
                None,
            )
            if existing is not None:
                existing.update(
                    {
                        "schedule": _get_mangled(params, "schedule") or existing.get("schedule", {}),
                        "active": _get_mangled(params, "active") or existing.get("active", True),
                        "updated_at": _get_mangled(params, "updated_at"),
                    }
                )
                return MockResult([MockRow(existing.copy())])

            sched_id = _schedules["next_id"]
            _schedules["next_id"] += 1
            record = {
                "id": sched_id,
                "tenant_id": tenant_id,
                "report_id": report_id,
                "schedule": _get_mangled(params, "schedule") or {},
                "active": _get_mangled(params, "active") or True,
                "created_at": _get_mangled(params, "created_at"),
                "updated_at": _get_mangled(params, "updated_at"),
            }
            _schedules["records"][sched_id] = record
            return MockResult([MockRow(record.copy())])

        # UPDATE: update schedule by id + tenant_id.
        if sql_text.startswith("update") and "report_schedules" in sql_text:
            sched_id = _get_schedule_id(params)
            if sched_id is None:
                return MockResult([])
            rec = _schedules["records"].get(sched_id)
            try:
                tenant_id = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            if rec is None or rec.get("tenant_id") != tenant_id:
                return MockResult([])
            return MockResult([MockRow(rec.copy())])

        # SELECT: list schedules for a tenant (covers schedule_report's existing-record check).
        if "select" in sql_text and "from report_schedules" in sql_text:
            try:
                tenant_id = _get_tenant_id(params)
            except _MissingTenantIdError:
                return MockResult([])
            report_id = _get_mangled(params, "report_id")
            rows = [
                MockRow(rec.copy())
                for rec in _schedules["records"].values()
                if rec.get("tenant_id") == tenant_id
                and (report_id is None or rec.get("report_id") == report_id)
            ]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_report_handler(state), make_schedule_handler(state)]


__all__ = ["get_handlers", "make_report_handler", "make_schedule_handler"]
