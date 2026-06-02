"""Ticket SQL handlers for unit tests."""

from __future__ import annotations

import re

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 50

# SQLAlchemy 2.x ORMs mangle WHERE-column bind names (e.g. 'id' → 'id_1').
# Strip the trailing _<digits> suffix so handlers can look up by plain column name.
_MANGLED_RE = re.compile(r"^(id|tenant_id|ticket_id|pipeline_id|customer_id|assigned_to|owner_id)(?:_\d+)$")


def make_ticket_handler(state: MockState) -> callable:
    state.opaque.setdefault("tickets", [])

    def handler(sql_text, params):
        if "insert into tickets" in sql_text:
            new_id = len(state.opaque["tickets"]) + 1
            row = {
                "id": params.get("id", new_id),
                "tenant_id": params.get("tenant_id", 0),
                "subject": params.get("subject", "Ticket"),
                "description": params.get("description"),
                "status": "open",
                "priority": params.get("priority", "medium"),
                "customer_id": params.get("customer_id", 1),
                "assignee_id": params.get("assignee_id"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.opaque["tickets"].append(row)
            return MockResult([MockRow(row)])

        if "from tickets" in sql_text:
            # Normalise SQLAlchemy 2.x mangle: 'id_1' → 'id', 'tenant_id_1' → 'tenant_id'
            norm = {}
            for k, v in params.items():
                m = _MANGLED_RE.match(k)
                norm[m.group(1) if m else k] = v
            tid = norm.get("id")
            tenant = norm.get("tenant_id")
            for row in state.opaque.get("tickets", []):
                # Require both id AND tenant to match (defense-in-depth for not-found case)
                if tid is not None and tenant is not None:
                    if row["id"] == tid and row["tenant_id"] == tenant:
                        return MockResult([MockRow(row)])
                elif tid is not None and row["id"] == tid:
                    return MockResult([MockRow(row)])
                elif tenant is not None and row["tenant_id"] == tenant:
                    return MockResult([MockRow(row)])
            return MockResult([])

        return None

    return handler


def get_handlers(state: MockState):
    return [make_ticket_handler(state)]


__all__ = ["get_handlers", "make_ticket_handler"]
