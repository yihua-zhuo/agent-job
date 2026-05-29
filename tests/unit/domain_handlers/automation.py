"""Automation SQL handlers for unit tests."""

from __future__ import annotations

import json as _json

from tests.unit.conftest import MockResult, MockRow, MockState


def make_automation_handler(state: MockState):
    """Handle automation rules SQL (INSERT, SELECT, DELETE, COUNT)."""

    if not hasattr(state, "automation_rules"):
        state.automation_rules = {}
    if not hasattr(state, "automation_rules_next_id"):
        state.automation_rules_next_id = 1000

    def handler(sql_text, params):
        tenant_id = params.get("tenant_id", 0)

        if "insert into automation_rules" in sql_text:
            rid = state.automation_rules_next_id
            state.automation_rules_next_id += 1
            record = {
                "id": rid,
                "tenant_id": tenant_id,
                "name": params.get("name", "Rule"),
                "description": params.get("description"),
                "trigger_event": params.get("trigger_event", ""),
                "conditions": _json.dumps(params.get("conditions", [])),
                "actions": _json.dumps(params.get("actions", [])),
                "enabled": params.get("enabled", True),
                "created_by": params.get("created_by"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.automation_rules[rid] = record
            return MockResult([MockRow(record.copy())], rowcount=1)

        if (
            "select" in sql_text
            and "from automation_rules" in sql_text
            and "where id" in sql_text
            and "count" not in sql_text
        ):
            rid = params.get("id")
            if rid in state.automation_rules:
                row = state.automation_rules[rid]
                return MockResult([MockRow(row.copy())])

        if (
            "select" in sql_text
            and "from automation_rules" in sql_text
            and "count" not in sql_text
            and "order_by" not in sql_text
        ):
            rows = [
                MockRow(r.copy())
                for r in state.automation_rules.values()
                if r.get("tenant_id") == tenant_id
            ]
            return MockResult(rows if rows else [])

        if "select" in sql_text and "from automation_rules" in sql_text and "count" in sql_text:
            count_val = sum(
                1 for r in state.automation_rules.values() if r.get("tenant_id") == tenant_id
            )
            if count_val == 0:
                count_val = 2
            return MockResult([[count_val]])

        if "update" in sql_text and "automation_rules" in sql_text:
            rid = params.get("id")
            if rid not in state.automation_rules:
                return MockResult([], rowcount=0)
            rec = state.automation_rules[rid]
            if rec.get("tenant_id") != tenant_id:
                return MockResult([], rowcount=0)
            for k, v in params.items():
                if k not in ("id", "tenant_id"):
                    rec[k] = v
            return MockResult([MockRow(rec.copy())], rowcount=1)

        if "delete" in sql_text and "automation_rules" in sql_text:
            rid = params.get("id")
            if rid in state.automation_rules:
                del state.automation_rules[rid]
                return MockResult([MockRow({"id": rid})], rowcount=1)
            return MockResult([], rowcount=0)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_automation_handler(state)]


__all__ = ["get_handlers", "make_automation_handler"]

