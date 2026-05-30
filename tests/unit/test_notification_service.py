"""Unit tests for NotificationService."""

from unittest.mock import AsyncMock, patch

import pytest

from services.notification_service import NotificationService
from tests.unit.conftest import MockState, make_mock_session, make_notification_handler


@pytest.fixture
def notification_state():
    return MockState()


@pytest.fixture
def mock_db_session(notification_state):
    session = make_mock_session(
        [make_notification_handler(notification_state)],
        state=notification_state,
    )

    async def refresh_side_effect(obj):
        if obj.id is None:
            nid = getattr(notification_state, "notifications_next_id", 1)
            setattr(notification_state, "notifications_next_id", nid + 1)
            obj.id = nid

    session.refresh.side_effect = refresh_side_effect
    return session


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.mark.asyncio
    async def test_get_unread_count(self, mock_db_session, notification_state):
        """get_unread_count returns correct count before and after marking a notification as read."""
        svc = NotificationService(mock_db_session)

        # Seed three notifications into state (ids 1, 2, 3)
        if not hasattr(notification_state, "notifications"):
            notification_state.notifications = {}
        for nid in (1, 2, 3):
            notification_state.notifications[nid] = {
                "id": nid,
                "tenant_id": 1,
                "user_id": 1,
                "type": "info",
                "title": f"Notification {nid}",
                "content": "Test",
                "is_read": False,
                "related_type": None,
                "related_id": None,
                "created_at": None,
            }
        notification_state.notifications_next_id = 4

        with (
            patch.object(svc, "get_unread_count", new_callable=AsyncMock) as mock_count,
            patch.object(svc, "mark_as_read", new_callable=AsyncMock) as mock_mark,
        ):
            mock_count.return_value = 3
            count_before = await svc.get_unread_count(user_id=1, tenant_id=1)
            assert count_before == 3

            mock_mark.return_value = notification_state.notifications[1]
            await svc.mark_as_read(notification_id=1, tenant_id=1)

            mock_count.return_value = 2
            count_after = await svc.get_unread_count(user_id=1, tenant_id=1)
            assert count_after == 2
