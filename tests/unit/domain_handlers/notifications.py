"""Notification SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def _get(params: dict, key: str, default=None):
    """Get a param, trying bare key first then key_N forms."""
    if key in params:
        return params[key]
    for k, v in params.items():
        if k.startswith("_") or k.startswith("param_"):
            continue
        # Strip trailing _N suffix (e.g. "id_1" -> "id", "tenant_id_2" -> "tenant_id")
        base = k
        while base and base[-1].isdigit():
            base = base[:-1]
        if base.endswith("_"):
            base = base[:-1]
        if base == key:
            return v
    return default


def make_notification_handler(state: MockState):
    """Handle all notification-related SQL (INSERT, UPDATE, SELECT)."""

    def handler(sql_text, params):
        # INSERT for send_notification
        if "insert into notifications" in sql_text:
            nid = getattr(state, "notifications_next_id", 1)
            setattr(state, "notifications_next_id", nid + 1)
            nid_str = str(nid)
            record = {
                "id": nid,
                "tenant_id": _get(params, "tenant_id", 0),
                "user_id": _get(params, "user_id", 0),
                "type": params.get("type"),
                "title": params.get("title"),
                "content": params.get("content"),
                "is_read": False,
                "related_type": params.get("related_type"),
                "related_id": params.get("related_id"),
                "created_at": params.get("created_at"),
            }
            if not hasattr(state, "notifications"):
                state.notifications = {}
            # Store by string key so string params (e.g. "id_1") match for lookup
            state.notifications[nid_str] = record
            return MockResult([MockRow(record.copy())])

        # SELECT ... count(*) for get_unread_count
        if "select" in sql_text and "from notifications" in sql_text and "count" in sql_text:
            tenant_id = _get(params, "tenant_id", 0)
            user_id = _get(params, "user_id", 0)
            notifications = getattr(state, "notifications", {})
            count = sum(
                1
                for n in notifications.values()
                if n.get("tenant_id") == tenant_id
                and n.get("user_id") == user_id
                and not n.get("is_read", False)
            )
            return MockResult([MockRow({"count": count}, _scalar=count)])

        # SELECT for mark_as_read (fetch by id + tenant_id)
        if "select" in sql_text and "from notifications" in sql_text and "where" in sql_text and "notifications.id" in sql_text and "count" not in sql_text:
            notification_id = _get(params, "id")
            tenant_id = _get(params, "tenant_id", 0)
            notifications = getattr(state, "notifications", {})
            # Key may be string (param "id_1") or int (state keys)
            key = str(notification_id) if notification_id is not None else None
            if key in notifications:
                rec = notifications[key].copy()
                rec["is_read"] = True
                notifications[key]["is_read"] = True
                return MockResult([MockRow(rec)])
            # fixture for ids >= 1 not in state
            if notification_id and int(notification_id) >= 1:
                return MockResult(
                    [
                        MockRow(
                            {
                                "id": int(notification_id),
                                "tenant_id": tenant_id,
                                "user_id": 1,
                                "type": "info",
                                "title": "Notification",
                                "content": "Test",
                                "is_read": True,
                                "related_type": None,
                                "related_id": None,
                                "created_at": None,
                            }
                        )
                    ]
                )
            return MockResult([])

        return None

    return handler


def get_handlers(state: MockState):
    return [make_notification_handler(state)]


__all__ = ["get_handlers", "make_notification_handler"]
