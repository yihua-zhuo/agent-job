"""Workflow instance SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def make_workflow_instance_handler(state: MockState):
    """Handle all workflow_instance-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into workflow_instances" in sql_text:
            wid = getattr(state, "workflow_instances_next_id", 1)
            if not hasattr(state, "workflow_instances_next_id"):
                state.workflow_instances_next_id = 1
                wid = 1
            state.workflow_instances_next_id += 1
            record = {
                "id": wid,
                "tenant_id": params.get("tenant_id", 0),
                "definition_id": params.get("definition_id", 1),
                "status": params.get("status", "pending"),
                "context": params.get("context", {}),
                # started_at is nullable with no server_default in the ORM model — params.get()
            # returns None when absent, matching real behavior. If the ORM later adds a
            # server_default, this mock will need updating to reflect auto-population.
            "started_at": params.get("started_at"),
                "completed_at": params.get("completed_at"),
            }
            if not hasattr(state, "workflow_instances"):
                state.workflow_instances = {}
            state.workflow_instances[wid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "workflow_instances" in sql_text:
            wid = params.get("id")
            if hasattr(state, "workflow_instances") and wid in state.workflow_instances:
                rec = state.workflow_instances[wid]
                if rec.get("tenant_id") != params.get("tenant_id"):
                    return MockResult([])
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if sql_text.startswith("delete") and "workflow_instances" in sql_text:
            if hasattr(state, "workflow_instances"):
                wid = params.get("id")
                rec = state.workflow_instances.get(wid)
                if rec is None or rec.get("tenant_id") != params.get("tenant_id"):
                    return MockResult([])
                del state.workflow_instances[wid]
            return MockResult([MockRow({"id": params.get("id", 1)})])

        if "select" in sql_text and "count" in sql_text and "from workflow_instances" in sql_text:
            tenant_id = params.get("tenant_id")
            rows = []
            if hasattr(state, "workflow_instances"):
                rows = [r for r in state.workflow_instances.values() if r.get("tenant_id") == tenant_id]
            return MockResult([[len(rows)]])

        if "from workflow_instances where id" in sql_text:
            wid = params.get("id")
            if hasattr(state, "workflow_instances") and wid in state.workflow_instances:
                rec = state.workflow_instances[wid]
                if rec.get("tenant_id") != params.get("tenant_id"):
                    return MockResult([])
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if "select" in sql_text and "from workflow_instances" in sql_text:
            tenant_filter = params.get("tenant_id", 0)
            rows = []
            if hasattr(state, "workflow_instances"):
                rows = [
                    MockRow(r.copy()) for r in state.workflow_instances.values() if r.get("tenant_id") == tenant_filter
                ]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_workflow_instance_handler(state)]


__all__ = ["get_handlers", "make_workflow_instance_handler"]
