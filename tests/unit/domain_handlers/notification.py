"""Notification SQL handlers for unit tests."""

from __future__ import annotations

ORDER = 2


def _notification_to_row(n: dict):
    from tests.unit.conftest import MockRow

    return MockRow(
        {
            "id": n.get("id"),
            "tenant_id": n.get("tenant_id"),
            "user_id": n.get("user_id"),
            "channel": n.get("channel"),
            "template": n.get("template"),
            "params_": n.get("params_"),
            "status": n.get("status"),
            "priority": n.get("priority"),
            "created_at": n.get("created_at"),
            "delivered_at": n.get("delivered_at"),
            "read_at": n.get("read_at"),
        }
    )


def make_notification_handler(state):
    """Return a handler that manages an in-memory notification store in state."""
    from tests.unit.conftest import MockResult

    def handler(sql_text: str, params: dict):
        # Initialise per-state store
        if not hasattr(state, "_notifications"):
            state._notifications = {}
            state._notifications_next_id = 1

        if "insert into notifications" in sql_text:
            nid = state._notifications_next_id
            state._notifications_next_id += 1
            n = {
                "id": nid,
                "tenant_id": params.get("tenant_id", 0),
                "user_id": params.get("user_id", 0),
                "channel": params.get("channel"),
                "template": params.get("template"),
                "params_": params.get("params_"),
                "status": params.get("status", "pending"),
                "priority": params.get("priority", "normal"),
                "created_at": params.get("created_at"),
                "delivered_at": None,
                "read_at": None,
            }
            state._notifications[nid] = n
            return MockResult([_notification_to_row(n)])

        if "from notifications where id" in sql_text:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id"):
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "update notifications" in sql_text and "read_at" in sql_text:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id"):
                n["read_at"] = params.get("read_at")
                n["status"] = "read"
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "from notifications" in sql_text and "count" not in sql_text:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = "read_at is null" in sql_text or "read_at = null" in sql_text
            page = params.get("offset", 0) // max(params.get("limit", 20), 1)
            page_size = params.get("limit", 20)
            rows = []
            for n in state._notifications.values():
                if n.get("tenant_id") != tenant_id or n.get("user_id") != user_id:
                    continue
                if unread_filter and n.get("read_at") is not None:
                    continue
                rows.append(n)
            offset = page * page_size
            return MockResult([_notification_to_row(r) for r in rows[offset : offset + page_size]])

        if "select" in sql_text and "count" in sql_text and "from notifications" in sql_text:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = "read_at is null" in sql_text or "read_at = null" in sql_text
            count = sum(
                1
                for n in state._notifications.values()
                if n.get("tenant_id") == tenant_id
                and n.get("user_id") == user_id
                and (not unread_filter or n.get("read_at") is None)
            )
            return MockResult([[count]])

        return None

    return handler


def get_handlers(state):
    return [make_notification_handler(state)]


__all__ = ["get_handlers", "make_notification_handler"]