"""Notification SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_notification_handler(state: MockState):
    """Handle all notification-related SQL (INSERT, UPDATE, SELECT)."""

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

        # SELECT for mark_as_read (fetch by id + tenant_id)
        if "select" in sql_text and "from notifications" in sql_text and "where id" in sql_text:
            notification_id = params.get("id")
            tenant_id = params.get("tenant_id", 0)
            notifications = getattr(state, "notifications", {})
            if notification_id in notifications:
                rec = notifications[notification_id].copy()
                rec["is_read"] = True
                notifications[notification_id]["is_read"] = True
                return MockResult([MockRow(rec)])
            # fixture for ids >= 1 not in state
            if notification_id and notification_id >= 1:
                return MockResult(
                    [
                        MockRow(
                            {
                                "id": notification_id,
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
