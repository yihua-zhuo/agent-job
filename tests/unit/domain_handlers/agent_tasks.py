"""Agent task SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_agent_task_handler(state: MockState):
    def handler(sql_text, params):
        # Normalize compiled SQLAlchemy params: strip trailing _<digit> from keys
        # (e.g. "id_1" -> "id", "tenant_id_1" -> "tenant_id").
        normalized = {}
        for k, v in params.items():
            import re
            base = re.sub(r"_\d+$", "", k)
            if base not in normalized:
                normalized[base] = v

        # INSERT
        if "insert into agent_tasks" in sql_text:
            # Skip if already inserted (flush called after a prior refresh set the id).
            existing_id = normalized.get("id")
            if existing_id is not None and existing_id in state.agent_tasks:
                return MockResult([MockRow(state.agent_tasks[existing_id].copy())])
            new_id = state.agent_tasks_next_id
            state.agent_tasks_next_id += 1
            record = {
                "id": new_id,
                "task_id": normalized.get("task_id") or params.get("task_id") or f"atask_{new_id}",
                "tenant_id": normalized.get("tenant_id") or 0,
                "description": normalized.get("description") or params.get("description"),
                "status": normalized.get("status") or "pending",
                "subtasks": normalized.get("subtasks") or params.get("subtasks") or [],
                "created_at": normalized.get("created_at") or params.get("created_at"),
                "updated_at": normalized.get("updated_at") or params.get("updated_at"),
            }
            state.agent_tasks[new_id] = record
            return MockResult([MockRow(record.copy())])

        # SELECT by id + tenant
        if "from agent_tasks where id" in sql_text and "tenant_id" in sql_text:
            tid = normalized.get("id")
            if tid in state.agent_tasks:
                return MockResult([MockRow(state.agent_tasks[tid].copy())])
            return MockResult([])

        # COUNT
        if "select" in sql_text and "count" in sql_text and "from agent_tasks" in sql_text:
            tenant_id = normalized.get("tenant_id", 0)
            count_val = sum(1 for r in state.agent_tasks.values() if r.get("tenant_id") == tenant_id)
            return MockResult([[count_val]])

        # SELECT list (no id filter)
        if "select" in sql_text and "from agent_tasks" in sql_text and "where id" not in sql_text:
            tenant_id = normalized.get("tenant_id", 0)
            rows = []
            for rec in state.agent_tasks.values():
                if rec.get("tenant_id") != tenant_id:
                    continue
                rows.append(MockRow(rec.copy()))
            # Parse offset/limit from named params (e.g. param_1=limit, param_2=offset).
            import re
            offset_val = None
            limit_val = None
            offset_match = re.search(r"offset\s*:?\s*(\w+)", sql_text)
            limit_match = re.search(r"limit\s*:?\s*(\w+)", sql_text)
            if offset_match is not None:
                offset_key = offset_match.group(1)
                offset_val = params.get(offset_key)
            if limit_match is not None:
                limit_key = limit_match.group(1)
                limit_val = params.get(limit_key)
            if offset_val is not None:
                rows = rows[offset_val:]
            if limit_val is not None:
                rows = rows[:limit_val]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_agent_task_handler(state)]


__all__ = ["get_handlers", "make_agent_task_handler"]
