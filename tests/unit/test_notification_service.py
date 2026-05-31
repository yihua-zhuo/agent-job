"""Unit tests for NotificationService."""

import pytest

from services.notification_service import NotificationService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.notifications import make_notification_handler


@pytest.fixture
def mock_db_session():
    state = MockState()
    handler = make_notification_handler(state)
    pending = []

    async def flush_handler():
        # Flush persists pending ORM objects via the handler so they appear in
        # state. ID assignment is deferred to refresh so the object and state
        # stay in sync (flush runs before refresh).
        for obj in pending[:]:
            handler(
                "insert into notifications",
                {
                    "tenant_id": getattr(obj, "tenant_id", 0),
                    "user_id": getattr(obj, "user_id", 0),
                    "type": getattr(obj, "type", None),
                    "title": getattr(obj, "title", ""),
                    "content": getattr(obj, "content", ""),
                    "related_type": getattr(obj, "related_type", None),
                    "related_id": getattr(obj, "related_id", None),
                    "created_at": getattr(obj, "created_at", None),
                },
            )
        pending.clear()

    async def refresh_handler(obj):
        # The ID was already assigned by the handler during flush (id is
        # incremented before storing). Sync the object attribute to match.
        nid = getattr(state, "notifications_next_id", 1) - 1
        obj.id = nid

    session = make_mock_session([handler], state=state)

    _add = session.add

    def tracked_add(obj):
        pending.append(obj)
        _add(obj)

    session.add = tracked_add
    session.flush = flush_handler
    session.refresh = refresh_handler
    return session


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.mark.asyncio
    async def test_get_unread_count(self, mock_db_session):
        """get_unread_count returns correct count before and after marking a notification as read."""
        svc = NotificationService(mock_db_session)

        # Send three notifications for user_id=99, tenant_id=1
        created = []
        for i in range(3):
            notification = await svc.send_notification(
                tenant_id=1,
                user_id=99,
                notification_type="info",
                title=f"Notification {i+1}",
                content="Test",
            )
            created.append(notification)

        # Verify initial unread count is 3
        count_before = await svc.get_unread_count(user_id=99, tenant_id=1)
        assert count_before == 3

        # Mark the first notification as read
        await svc.mark_as_read(notification_id=created[0].id, tenant_id=1)

        # Verify count decreased to 2
        count_after = await svc.get_unread_count(user_id=99, tenant_id=1)
        assert count_after == 2
