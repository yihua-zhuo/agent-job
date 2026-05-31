"""Notification SQL handler for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_notification_handler(state: MockState):
    """Handle notification SQL: INSERT for send_notification, SELECT/COUNT for unread queries."""

    def handler(sql_text, params):
        # INSERT for send_notification
        if "insert into notifications" in sql_text:
            nid = getattr(state, "notifications_next_id", 1)
            setattr(state, "notifications_next_id", nid + 1)
            record = {
                "id": nid,
                "tenant_id": params.get("tenant_id", 0),
                "user_id": params.get("user_id", 0),
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
            state.notifications[nid] = record
            return MockResult([MockRow(record.copy())])

        # SELECT ... count(*) for get_unread_count
        if "select" in sql_text and "from notifications" in sql_text and "count" in sql_text:
            # SQLAlchemy compiler may generate tenant_id_1 / user_id_1 when joining tables,
            # so accept both plain names and _N suffixes for the same ID
            tenant_id = params.get("tenant_id") or params.get("tenant_id_1") or params.get("tenant_id_2") or 0
            user_id = params.get("user_id") or params.get("user_id_1") or params.get("user_id_2") or 0
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
        if (
            "select" in sql_text
            and "from notifications" in sql_text
            and "where" in sql_text
            and "notifications.id" in sql_text
            and "count" not in sql_text
        ):
            # SQLAlchemy compiler generates id_1 / tenant_id_1 when joining tables
            notification_id = params.get("id") or params.get("id_1")
            tenant_id = params.get("tenant_id") or params.get("tenant_id_1") or 0
            notifications = getattr(state, "notifications", {})
            key = int(notification_id) if notification_id is not None else None
            if key is not None and key in notifications:
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
                                "type": "email",
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
