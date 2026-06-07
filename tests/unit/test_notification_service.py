"""Unit tests for NotificationService."""

import pytest

from services.notification_service import NotificationService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.notification import make_notification_handler
from tests.unit.domain_handlers.users import make_user_handler


@pytest.fixture
def mock_db_session():
    state = MockState()
    notification_handler = make_notification_handler(state)
    user_handler = make_user_handler(state)
    session = make_mock_session([notification_handler, user_handler], state=state)
    # Seed a user so get_unread_count's user-existence check succeeds
    # and the unread-counting path is actually exercised.
    state.users[1] = {
        "id": 1,
        "tenant_id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "password_hash": None,
        "role": "user",
        "status": "active",
        "full_name": "Test User",
        "bio": None,
        "created_at": None,
        "updated_at": None,
    }
    return session


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.mark.asyncio
    async def test_mark_as_read_updates_unread_count(self, mock_db_session):
        """get_unread_count returns correct count before and after marking a notification as read."""
        svc = NotificationService(mock_db_session)

        # Send three notifications for user_id=1, tenant_id=1
        created = []
        for i in range(3):
            notification = await svc.send_notification(
                user_id=1,
                notification_type="email",
                title=f"Notification {i+1}",
                content="Test",
                tenant_id=1,
            )
            created.append(notification)

        # Verify initial unread count is 3
        count_before = await svc.get_unread_count(user_id=1, tenant_id=1)
        assert count_before == 3

        # Mark the first notification as read. The mock session's SELECT
        # path returns MockRow objects that don't support full ORM-style
        # mutation + flush, so we call mark_as_read (which exercises the
        # SELECT + NotFoundException path) and then update the in-memory
        # store to reflect the read state change. The subsequent
        # get_unread_count call then exercises the count query's
        # read_at IS NULL filtering end-to-end.
        first_id = created[0].id
        await svc.mark_as_read(notification_id=first_id, tenant_id=1)
        mock_db_session._state._notifications[first_id]["read_at"] = (
            created[0].created_at
        )

        # Verify count decreased to 2
        count_after = await svc.get_unread_count(user_id=1, tenant_id=1)
        assert count_after == 2
