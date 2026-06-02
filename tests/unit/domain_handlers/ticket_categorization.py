"""Ticket categorization domain SQL mock handlers for unit tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 55

_TICKET_ID_RE = re.compile(r"\bticket_categorizations\.ticket_id\s*=\s*(\d+)", re.IGNORECASE)
_TENANT_ID_RE = re.compile(r"\bticket_categorizations\.tenant_id\s*=\s*(\d+)", re.IGNORECASE)


def make_ticket_categorization_handler(state: MockState) -> callable:
    state.opaque.setdefault("ticket_categorizations", [])

    def handler(sql_text, params):
        if "insert into ticket_categorizations" in sql_text:
            rows = state.opaque["ticket_categorizations"]
            new_id = len(rows) + 1
            now = datetime.now(UTC)
            row = {
                "id": new_id,
                "tenant_id": params.get("tenant_id"),
                "ticket_id": params.get("ticket_id"),
                "category_type": params.get("category_type", "uncategorized"),
                "priority": params.get("priority"),
                "confidence": params.get("confidence"),
                "reasons": params.get("reasons"),
                "suggested_assignee_id": params.get("suggested_assignee_id"),
                "suggested_team": params.get("suggested_team"),
                "human_override": params.get("human_override", False),
                "categorized_at": params.get("categorized_at"),
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            return MockResult([MockRow({"id": new_id})])

        if "from ticket_categorizations" in sql_text:
            rows = state.opaque["ticket_categorizations"]
            id_val = params.get("id")
            ticket_id_val = params.get("ticket_id")
            tenant_id_val = params.get("tenant_id")
            if not id_val:
                for row in rows:
                    if (
                        ticket_id_val
                        and row["ticket_id"] == ticket_id_val
                        and (tenant_id_val is None or row["tenant_id"] == tenant_id_val)
                    ):
                        return MockResult([MockRow(row)])
            for row in rows:
                if id_val and row["id"] == id_val:
                    return MockResult([MockRow(row)])
                if (
                    ticket_id_val
                    and row["ticket_id"] == ticket_id_val
                    and tenant_id_val
                    and row["tenant_id"] == tenant_id_val
                ):
                    return MockResult([MockRow(row)])
            return MockResult([])

        return None

    return handler


def get_handlers(state: MockState):
    return [make_ticket_categorization_handler(state)]


__all__ = ["get_handlers", "make_ticket_categorization_handler"]
