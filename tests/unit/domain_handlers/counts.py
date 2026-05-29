"""Fallback SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockState

ORDER = 1000


def make_count_handler(state: MockState):
    """Fallback COUNT handler for queries not caught by domain handlers."""

    def handler(sql_text, params):
        if "select" not in sql_text or "count" not in sql_text:
            return None
        tenant_id = params.get("tenant_id")
        count_val = 7 if tenant_id == 1 else 3
        return MockResult([[count_val]])

    return handler


def get_handlers(state: MockState):
    return [make_count_handler(state)]


__all__ = ["get_handlers", "make_count_handler"]
