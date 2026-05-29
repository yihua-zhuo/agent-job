"""Notification SQL handlers for unit tests."""

from __future__ import annotations


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


def _reminder_to_row(r: dict):
    from tests.unit.conftest import MockRow

    return MockRow(
        {
            "id": r.get("id"),
            "tenant_id": r.get("tenant_id"),
            "user_id": r.get("user_id"),
            "title": r.get("title"),
            "content": r.get("content"),
            "remind_at": r.get("remind_at"),
            "related_type": r.get("related_type"),
            "related_id": r.get("related_id"),
            "is_completed": r.get("is_completed", False),
            "created_at": r.get("created_at"),
        }
    )


def make_notification_handler(state):
    """Return a handler that manages an in-memory notification store in state."""
    from tests.unit.conftest import MockResult

    def handler(sql_text: str, params: dict):
        sql_text_lower = sql_text.lower()
        # Initialise per-state store
        if not hasattr(state, "_notifications"):
            state._notifications = {}
            state._notifications_next_id = 1

        if "insert into notifications" in sql_text_lower:
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

        if "from notifications where id" in sql_text_lower:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if (
                n
                and n.get("tenant_id") == params.get("tenant_id")
                and n.get("user_id") == params.get("user_id")
            ):
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "update notifications" in sql_text_lower and "read_at" in sql_text_lower:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id"):
                n["read_at"] = params.get("read_at")
                n["status"] = "read"
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "from notifications" in sql_text_lower and "count" not in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            # Fail open: if the SQL doesn't contain a recognizable unread pattern, return all rows
            unread_filter = "read_at is null" in sql_text_lower or "read_at = null" in sql_text_lower
            page_size = max(params.get("limit", 20), 1)
            offset = max(params.get("offset", 0), 0)
            rows = []
            for n in state._notifications.values():
                if n.get("tenant_id") != tenant_id or n.get("user_id") != user_id:
                    continue
                if unread_filter and n.get("read_at") is not None:
                    continue
                rows.append(n)
            return MockResult([_notification_to_row(r) for r in rows[offset : offset + page_size]])

        if "select count" in sql_text_lower and "from notifications" in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = "read_at is null" in sql_text_lower or "read_at = null" in sql_text_lower
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


def make_reminder_handler(state):
    """Return a handler that manages an in-memory reminder store in state."""
    from tests.unit.conftest import MockResult

    def handler(sql_text: str, params: dict):
        sql_text_lower = sql_text.lower()
        if not hasattr(state, "_reminders"):
            state._reminders = {}
            state._reminders_next_id = 1

        if "insert into reminders" in sql_text_lower:
            rid = state._reminders_next_id
            state._reminders_next_id += 1
            r = {
                "id": rid,
                "tenant_id": params.get("tenant_id", 0),
                "user_id": params.get("user_id", 0),
                "title": params.get("title"),
                "content": params.get("content"),
                "remind_at": params.get("remind_at"),
                "related_type": params.get("related_type"),
                "related_id": params.get("related_id"),
                "is_completed": params.get("is_completed", False),
                "created_at": params.get("created_at"),
            }
            state._reminders[rid] = r
            return MockResult([_reminder_to_row(r)])

        if "from reminders where id" in sql_text_lower and "delete" not in sql_text_lower:
            rid = params.get("id")
            r = state._reminders.get(rid)
            if r and r.get("tenant_id") == params.get("tenant_id"):
                return MockResult([_reminder_to_row(r)])
            return MockResult([])

        if "delete from reminders" in sql_text_lower:
            rid = params.get("id")
            r = state._reminders.get(rid)
            if r and r.get("tenant_id") == params.get("tenant_id"):
                del state._reminders[rid]
                return MockResult([], rowcount=1)
            return MockResult([], rowcount=0)

        if "from reminders" in sql_text_lower and "count" not in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            rows = [
                r
                for r in state._reminders.values()
                if r.get("tenant_id") == tenant_id and r.get("user_id") == user_id
            ]
            return MockResult([_reminder_to_row(r) for r in rows])

        return None

    return handler


def get_handlers(state):
    return [make_notification_handler(state), make_reminder_handler(state)]


__all__ = ["get_handlers", "make_notification_handler", "make_reminder_handler"]
