"""Notification SQL handlers for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.unit.conftest import MockResult, MockRow

# SQLAlchemy bind parameter name for the notification params JSON column.
_NOTIFICATION_PARAMS_KEY = "params_"


def _notification_to_row(n: dict):
    return MockRow(
        {
            "id": n.get("id"),
            "tenant_id": n.get("tenant_id"),
            "user_id": n.get("user_id"),
            "channel": n.get("channel"),
            "template": n.get("template"),
            _NOTIFICATION_PARAMS_KEY: n.get("params_"),
            "status": n.get("status"),
            "priority": n.get("priority"),
            "created_at": n.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC),
            "delivered_at": n.get("delivered_at"),
            "read_at": n.get("read_at"),
        }
    )


def _reminder_to_row(r: dict):
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

    def handler(sql_text: str, params: dict[str, Any]) -> MockResult | None:
        if not hasattr(state, "_notifications"):
            state._notifications = {}
            state._notifications_next_id = 1
        sql_text_lower = sql_text.lower()

        if "insert into notifications" in sql_text_lower:
            # No enforcement needed — the service sets payload_params as an ORM
            # attribute, not as a raw SQL bind parameter; params_ is populated by
            # SQLAlchemy's ORM machinery, not directly from the SQL bind dict.
            nid = state._notifications_next_id
            state._notifications_next_id += 1
            n = {
                "id": nid,
                "tenant_id": params.get("tenant_id", 0),
                "user_id": params.get("user_id", 0),
                "channel": params.get("channel"),
                "template": params.get("template"),
                "params_": params.get(_NOTIFICATION_PARAMS_KEY),
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
            if n and n.get("tenant_id") == params.get("tenant_id"):
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "count(" in sql_text_lower and "from notifications" in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = "read_at is null" in sql_text_lower
            count = sum(
                1
                for n in state._notifications.values()
                if n.get("tenant_id") == tenant_id
                and n.get("user_id") == user_id
                and (not unread_filter or n.get("read_at") is None)
            )
            return MockResult([[count]])

        if "from notifications" in sql_text_lower and "count" not in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = "read_at is null" in sql_text_lower
            page_size = max(params.get("limit", 20), 1)
            offset = max(params.get("offset", 0), 0)
            rows = []
            for n in state._notifications.values():
                if n.get("tenant_id") != tenant_id:
                    continue
                if n.get("user_id") != user_id:
                    continue
                if unread_filter and n.get("read_at") is not None:
                    continue
                rows.append(n)
            return MockResult([_notification_to_row(r) for r in rows[offset : offset + page_size]])

        if "update notifications" in sql_text_lower and "read_at" in sql_text_lower:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id"):
                n["read_at"] = params.get("read_at")
                n["status"] = "read"
                return MockResult([_notification_to_row(n)])
            return MockResult([])

        if "delete from notifications" in sql_text_lower:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id"):
                del state._notifications[nid]
                return MockResult([], rowcount=1)
            return MockResult([], rowcount=0)

        if "notifications" in sql_text_lower:
            # Within the notification domain but pattern not recognised — fail loudly.
            raise ValueError(f"Unhandled notification SQL pattern: {sql_text[:80]}")

        # SQL targets a different domain — fall through so other handlers can respond.
        return None

    return handler


def make_reminder_handler(state):
    """Return a handler that manages an in-memory reminder store in state."""

    def handler(sql_text: str, params: dict[str, Any]) -> MockResult | None:
        if not hasattr(state, "_reminders"):
            state._reminders = {}
            state._reminders_next_id = 1
        sql_text_lower = sql_text.lower()

        if "insert into reminders" in sql_text_lower:
            assert "tenant_id" in params and "user_id" in params, (
                f"insert must bind tenant_id and user_id (got keys: {list(params.keys())})"
            )
            rid = state._reminders_next_id
            state._reminders_next_id += 1
            r = {
                "id": rid,
                "tenant_id": params.get("tenant_id"),
                "user_id": params.get("user_id"),
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
                if r.get("is_completed"):
                    # Completed reminders cannot be cancelled.
                    return MockResult([], rowcount=0)
                del state._reminders[rid]
                return MockResult([], rowcount=1)
            return MockResult([], rowcount=0)

        if "from reminders" in sql_text_lower and "count" not in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            # is_completed_filter comes from params (set by the service via upcoming_only).
            # When "is_completed" is absent from params, upcoming_only=True was used server-side
            # (service appended is_completed==False as a bound param). We treat is_completed=None
            # in params as a signal to exclude completed reminders by default.
            is_completed_filter = params.get("is_completed")
            now = datetime.now(UTC)
            upcoming_only = "is_completed" not in params
            page_size = max(params.get("limit", 20), 1)
            offset = max(params.get("offset", 0), 0)
            rows = [
                r
                for r in state._reminders.values()
                if r.get("tenant_id") == tenant_id
                and r.get("user_id") == user_id
                and (
                    is_completed_filter is None
                    or r.get("is_completed") == is_completed_filter
                )
                and not (upcoming_only and (r.get("is_completed") or (r.get("remind_at") and r.get("remind_at") <= now)))
            ]
            return MockResult([_reminder_to_row(r) for r in rows[offset : offset + page_size]])

        if "reminders" in sql_text_lower:
            raise ValueError(f"Unhandled reminder SQL pattern: {sql_text[:80]}")

        return None

    return handler


def get_handlers(state):
    return [make_notification_handler(state), make_reminder_handler(state)]


__all__ = ["get_handlers", "make_notification_handler", "make_reminder_handler"]
