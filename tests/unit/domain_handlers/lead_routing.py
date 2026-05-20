"""Lead routing SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def make_routing_rule_handler(state: MockState):
    """Handle all routing_rule-related SQL (stateful)."""

    if not hasattr(state, "routing_rules"):
        state.routing_rules = {}
    if not hasattr(state, "routing_rules_next_id"):
        state.routing_rules_next_id = 1

    def handler(sql_text, params):
        if "insert into routing_rules" in sql_text:
            rid = state.routing_rules_next_id
            state.routing_rules_next_id += 1
            record = {
                "id": rid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Rule"),
                "conditions_json": params.get("conditions_json", []),
                "assignee_type": params.get("assignee_type", "round_robin"),
                "assignee_id": params.get("assignee_id"),
                "priority": params.get("priority", 0),
                "is_active": params.get("is_active", True),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.routing_rules[rid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "routing_rules" in sql_text:
            rid = params.get("id")
            tenant_id = params.get("tenant_id")
            if rid in state.routing_rules and state.routing_rules[rid].get("tenant_id") == tenant_id:
                rec = state.routing_rules[rid]
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        if sql_text.startswith("delete") and "routing_rules" in sql_text:
            rid = params.get("id")
            tenant_id = params.get("tenant_id")
            if rid in state.routing_rules and state.routing_rules[rid].get("tenant_id") == tenant_id:
                del state.routing_rules[rid]
                return MockResult([MockRow({"id": rid})])
            return MockResult([])

        if "select" in sql_text and "count" in sql_text and "from routing_rules" in sql_text:
            tenant_id = params.get("tenant_id", 0)
            count_val = sum(
                1 for r in state.routing_rules.values() if r.get("tenant_id") == tenant_id
            )
            if count_val == 0:
                count_val = 2
            return MockResult([[count_val]])

        if "from routing_rules" in sql_text and "where id" in sql_text:
            rid = params.get("id")
            tenant_id = params.get("tenant_id")
            if rid in state.routing_rules and state.routing_rules[rid].get("tenant_id") == tenant_id:
                return MockResult([MockRow(state.routing_rules[rid].copy())])
            fixtures = {
                1: {
                    "id": 1,
                    "tenant_id": 1,
                    "name": "APAC Rule",
                    "conditions_json": [{"field": "region", "operator": "in", "value": ["APAC"]}],
                    "assignee_type": "user",
                    "assignee_id": 5,
                    "priority": 100,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                },
            }
            if rid in fixtures:
                return MockResult([MockRow(fixtures[rid].copy())])
            return MockResult([])

        if "select" in sql_text and "from routing_rules" in sql_text and "where id" not in sql_text:
            tenant_id = params.get("tenant_id", 0)
            rows = [
                MockRow(rec.copy())
                for rec in state.routing_rules.values()
                if rec.get("tenant_id") == tenant_id
            ]
            if not rows:
                rows.append(
                    MockRow(
                        {
                            "id": 1,
                            "tenant_id": tenant_id,
                            "name": "APAC Rule",
                            "conditions_json": [
                                {"field": "region", "operator": "in", "value": ["APAC"]}
                            ],
                            "assignee_type": "user",
                            "assignee_id": 5,
                            "priority": 100,
                            "is_active": True,
                            "created_at": None,
                            "updated_at": None,
                        }
                    )
                )
            return MockResult(rows)

        return None

    return handler


def make_lead_routing_handler(state: MockState):
    """Handle lead routing state (round-robin cursor per tenant)."""

    if not hasattr(state, "round_robin_cursor"):
        state.round_robin_cursor = {}

    def handler(sql_text, params):
        if "routing_cursor" in sql_text or "round_robin" in sql_text:
            return MockResult([])
        return None

    return handler


def get_handlers(state: MockState):
    return [make_routing_rule_handler(state), make_lead_routing_handler(state)]


__all__ = ["get_handlers", "make_lead_routing_handler", "make_routing_rule_handler"]

