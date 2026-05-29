"""Campaign SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 60


def campaign_handler(sql_text, params):
    """Handle campaign-related SQL."""
    if "insert into campaigns" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": params.get("tenant_id", 0), "name": params.get("name", "Campaign"), "campaign_type": params.get("campaign_type", "email"), "status": "draft", "created_by": params.get("created_by"), "created_at": params.get("created_at"), "updated_at": params.get("updated_at")})])

    if "from campaigns" in sql_text:
        return MockResult([MockRow({"id": 1, "tenant_id": 1, "name": "Campaign A", "campaign_type": "email", "status": "draft", "created_by": 1, "created_at": None, "updated_at": None})])

    return None


def get_handlers(state: MockState):
    return [campaign_handler]


__all__ = ["campaign_handler", "get_handlers"]
