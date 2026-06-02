"""Workflow definition SQL handlers for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.unit.conftest import MockResult, MockRow, MockState


def make_workflow_definition_handler(state: MockState):
    """Handle all workflow_definition-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into workflow_definitions" in sql_text:
            wid = getattr(state, "workflow_definitions_next_id", 1)
            if not hasattr(state, "workflow_definitions_next_id"):
                state.workflow_definitions_next_id = 1
                wid = 1
            state.workflow_definitions_next_id += 1
            now_ts = datetime.now(UTC).isoformat()
            record = {
                "id": wid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Test Definition"),
                "description": params.get("description"),
                "version": params.get("version", "1.0"),
                "definition_data": params.get("definition_data", {}),
                "created_at": now_ts,
                "updated_at": now_ts,
            }
            if not hasattr(state, "workflow_definitions"):
                state.workflow_definitions = {}
            state.workflow_definitions[wid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "workflow_definitions" in sql_text:
            wid = params.get("id")
            if hasattr(state, "workflow_definitions") and wid in state.workflow_definitions:
                rec = state.workflow_definitions[wid]
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if sql_text.startswith("delete") and "workflow_definitions" in sql_text:
            if hasattr(state, "workflow_definitions"):
                wid = params.get("id")
                rec = state.workflow_definitions.get(wid)
                if rec is None or rec.get("tenant_id") != params.get("tenant_id"):
                    return MockResult([])
                del state.workflow_definitions[wid]
            return MockResult([MockRow({"id": params.get("id", 1)})])

        if "select" in sql_text and "count" in sql_text and "from workflow_definitions" in sql_text:
            tenant_id = params.get("tenant_id")
            rows = []
            if hasattr(state, "workflow_definitions"):
                rows = [r for r in state.workflow_definitions.values() if r.get("tenant_id") == tenant_id]
            return MockResult([[len(rows)]])

        if "from workflow_definitions where id" in sql_text:
            wid = params.get("id")
            if hasattr(state, "workflow_definitions") and wid in state.workflow_definitions:
                rec = state.workflow_definitions[wid]
                if rec.get("tenant_id") != params.get("tenant_id"):
                    return MockResult([])
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if "select" in sql_text and "from workflow_definitions" in sql_text:
            tenant_filter = params.get("tenant_id", 0)
            rows = []
            if hasattr(state, "workflow_definitions"):
                rows = [
                    MockRow(r.copy())
                    for r in state.workflow_definitions.values()
                    if r.get("tenant_id") == tenant_filter
                ]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_workflow_definition_handler(state)]


__all__ = ["get_handlers", "make_workflow_definition_handler"]
