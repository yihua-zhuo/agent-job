"""Notification SQL handlers for unit tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from tests.unit.conftest import MockResult, MockRow, MockState

# SQLAlchemy uses the Python attribute name as the bind parameter name for mapped
# attributes. payload_params maps to DB column `params_`, but the bind key is
# the Python attribute name: "payload_params".
_NOTIFICATION_PARAMS_KEY = "payload_params"


def _notification_to_row(n: dict):
    return MockRow(
        {
            "id": n.get("id"),
            "tenant_id": n.get("tenant_id"),
            "user_id": n.get("user_id"),
            "channel": n.get("channel"),
            "template": n.get("template"),
            "payload_params": n.get("payload_params"),
            "status": n.get("status"),
            "priority": n.get("priority"),
            "created_at": n.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC),
            "delivered_at": n.get("delivered_at"),
            "read_at": n.get("read_at"),
        }
    )


def _reminder_matches_filter(
    r: dict,
    *,
    tenant_id: int,
    user_id: int,
    is_completed_filter: bool | None,
    upcoming_only: bool,
    now: datetime,
) -> bool:
    """Determine whether a reminder row matches the list-reminders filter criteria.

    Composition semantics:
    - Tenant/user identity are always required.
    - is_completed_filter=None means "no filter on completion status" (include both).
    - When upcoming_only=True (default), completed reminders are excluded, and
      reminders whose remind_at time has already passed are also excluded.
    - When upcoming_only=False, only the is_completed filter applies.
    """
    if r.get("tenant_id") != tenant_id:
        return False
    if r.get("user_id") != user_id:
        return False
    if is_completed_filter is not None and r.get("is_completed") != is_completed_filter:
        return False
    if upcoming_only:
        if r.get("is_completed"):
            return False
        remind_at = r.get("remind_at")
        if remind_at and remind_at < now:
            return False
    return True


def make_notification_handler(state):
    """Return a handler that manages an in-memory notification store in state."""

    def handler(sql_text: str, params: dict[str, Any]) -> MockResult | None:
        if not hasattr(state, "_notifications"):
            state._notifications = {}
            state._notifications_next_id = 1
        sql_text_lower = sql_text.lower()

        if "insert into notifications" in sql_text_lower:
            # The service sets payload_params as an ORM attribute; SQLAlchemy uses
            # the Python attribute name "payload_params" as the bind key.
            # params_ is the DB column name; the ORM populates it internally.
            nid = state._notifications_next_id
            state._notifications_next_id += 1
            n = {
                "id": nid,
                "tenant_id": params.get("tenant_id", 0),
                "user_id": params.get("user_id", 0),
                "channel": params.get("channel"),
                "template": params.get("template"),
                "params_": params.get("payload_params"),
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
            # Explicit unread_only param takes precedence; fall back to SQL text heuristic
            # for tests using raw SQL text matching (backward compat).
            if "_unread_only" in params:
                unread_filter = params["_unread_only"]
            else:
                unread_filter = "read_at" in sql_text_lower and "null" in sql_text_lower
            if unread_filter:
                count = sum(
                    1
                    for n in state._notifications.values()
                    if n.get("tenant_id") == tenant_id and n.get("user_id") == user_id and n.get("read_at") is None
                )
            else:
                count = sum(
                    1
                    for n in state._notifications.values()
                    if n.get("tenant_id") == tenant_id and n.get("user_id") == user_id
                )
            return MockResult([[count]])

        if "from notifications" in sql_text_lower and "count" not in sql_text_lower:
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            unread_filter = params.get("_unread_only", False)
            page_size = max(params.get("limit", 20), 1)
            offset = max(params.get("offset", 0), 0)
            rows = sorted(
                (
                    n
                    for n in state._notifications.values()
                    if n.get("tenant_id") == tenant_id
                    and n.get("user_id") == user_id
                    and not (unread_filter and n.get("read_at") is not None)
                ),
                key=lambda n: n.get("id", 0),
            )
            return MockResult([_notification_to_row(r) for r in rows[offset : offset + page_size]])

        if "update notifications" in sql_text_lower and "read_at" in sql_text_lower:
            nid = params.get("id")
            n = state._notifications.get(nid)
            if n and n.get("tenant_id") == params.get("tenant_id") and n.get("user_id") == params.get("user_id"):
                n["read_at"] = params.get("read_at")
                if params.get("read_at") is not None:
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

        if "count(" in sql_text_lower and "from reminders" in sql_text_lower:
            assert "user_id" in params and "tenant_id" in params, (
                f"reminder count must bind user_id and tenant_id (got keys: {list(params.keys())})"
            )
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            count = sum(
                1 for r in state._reminders.values() if r.get("tenant_id") == tenant_id and r.get("user_id") == user_id
            )
            return MockResult([[count]])

        if "from reminders" in sql_text_lower and "count" not in sql_text_lower:
            assert "user_id" in params and "tenant_id" in params, (
                f"list-reminders must bind user_id and tenant_id (got keys: {list(params.keys())})"
            )
            tenant_id = params.get("tenant_id")
            user_id = params.get("user_id")
            # is_completed_filter comes from params (set by the service).
            # Contract: upcoming_only=True → service binds is_completed=False explicitly.
            #           upcoming_only=False → service binds no is_completed at all (None).
            # This means upcoming_only=True produces is_completed=False and upcoming_only=False
            # produces is_completed=None. Deriving upcoming_only via `is False` is therefore
            # correct but fragile — it breaks if the service ever passes is_completed=False
            # in a non-upcoming-only query. A dedicated _upcoming_only bool param would be
            # cleaner and is worth considering if the service signature is refactored.
            is_completed_filter = params.get("is_completed")
            now = params.get("_now", datetime.now(UTC))
            upcoming_only = params.get("_upcoming_only", is_completed_filter is False)
            page_size = max(params.get("limit", 20), 1)
            offset = max(params.get("offset", 0), 0)
            rows = [
                r
                for r in state._reminders.values()
                if _reminder_matches_filter(
                    r,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    is_completed_filter=is_completed_filter,
                    upcoming_only=upcoming_only,
                    now=now,
                )
            ]
            return MockResult([_reminder_to_row(r) for r in rows[offset : offset + page_size]])

        if "reminders" in sql_text_lower:
            raise ValueError(f"Unhandled reminder SQL pattern: {sql_text[:80]}")

        return None

    return handler


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
            "created_at": r.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC),
        }
    )


def get_handlers(state: MockState) -> list[Callable[[str, dict], MockResult | None]]:
    handlers = [make_notification_handler(state), make_reminder_handler(state)]
    # Deduplicate in case notification.py is listed alongside domain-specific modules
    # that also export overlapping handlers (Rule 135).
    seen_ids = set()
    unique = []
    for h in handlers:
        if id(h) not in seen_ids:
            seen_ids.add(id(h))
            unique.append(h)
    return unique


__all__ = ["get_handlers", "make_notification_handler", "make_reminder_handler"]
