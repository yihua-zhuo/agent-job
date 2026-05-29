"""Ticket SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 50


def ticket_sql_handler(sql_text, params):
    """Handle ticket-related SQL."""
    if "insert into tickets" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": params.get("tenant_id", 0), "subject": params.get("subject", "Ticket"), "description": params.get("description"), "status": "open", "priority": params.get("priority", "medium"), "customer_id": 1, "assignee_id": params.get("assignee_id"), "created_at": params.get("created_at"), "updated_at": params.get("updated_at")})])

    if "from tickets" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": 1, "subject": "Issue A", "description": "Desc", "status": "open", "priority": "medium", "customer_id": 1, "assignee_id": 1, "created_at": None, "updated_at": None})])

    return None


def get_handlers(state: MockState):
    return [ticket_sql_handler]


__all__ = ["get_handlers", "ticket_sql_handler"]
