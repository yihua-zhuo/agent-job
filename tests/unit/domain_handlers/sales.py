"""Sales SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 40


def pipeline_handler(sql_text, params):
    """Handle pipeline-related SQL."""
    if "insert into pipelines" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": params.get("tenant_id", 0), "name": params.get("name", "Pipeline"), "description": params.get("description"), "is_active": True, "created_at": params.get("created_at"), "updated_at": params.get("updated_at")})])

    if "from pipelines" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": 1, "name": "Pipeline A", "description": "Desc", "is_active": True, "created_at": None, "updated_at": None})])

    return None


def opportunity_handler(sql_text, params):
    """Handle opportunity-related SQL."""
    if "insert into opportunities" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": params.get("tenant_id", 0), "customer_id": 1, "title": params.get("title", "Opportunity"), "amount": params.get("amount", 1000), "stage": "qualification", "probability": 20, "owner_id": params.get("owner_id", 0), "expected_close_date": params.get("expected_close_date"), "created_at": params.get("created_at"), "updated_at": params.get("updated_at")})])

    if "from opportunities" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": 1, "customer_id": 1, "title": "Opportunity A", "amount": 1000, "stage": "qualification", "probability": 20, "owner_id": 1, "expected_close_date": None, "created_at": None, "updated_at": None})])

    return None


def get_handlers(state: MockState):
    return [pipeline_handler, opportunity_handler]


__all__ = ["get_handlers", "opportunity_handler", "pipeline_handler"]
