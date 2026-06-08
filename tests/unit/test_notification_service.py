"""Unit tests for NotificationService."""

import pytest

from pkg.errors.app_exceptions import NotFoundException
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
    # NOTE: state.users[1] is seeded directly to bypass the user handler's
    # INSERT path (which would default tenant_id to 0). The tenant_id field
    # below is the one validated by the SELECT handler — the user handler's
    # INSERT path is not exercised by this test.
    state.users[1] = {
        "id": 1,
        "tenant_id": 1,
        "username": "testuser",
        "email": "test@example.com",
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
    async def test_get_unread_count(self, mock_db_session):
        """get_unread_count returns correct count after marking a notification as read.

        Exercises the real service code path: send_notification flushes an
        INSERT (auto-increment ID), get_unread_count runs the COUNT query,
        mark_as_read does SELECT → in-place mutation → flush, and a second
        get_unread_count validates the read_at IS NULL filter by observing
        the count drop from 3 to 2.
        """
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

        # mark_as_read selects the notification, mutates read_at/status
        # in-place, and flushes. The handler's mutable row shares the store
        # dict, so the mutation propagates and get_unread_count observes
        # the transition end-to-end.
        first_id = created[0].id
        await svc.mark_as_read(notification_id=first_id, tenant_id=1)

        # Verify count decreased to 2
        count_after = await svc.get_unread_count(user_id=1, tenant_id=1)
        assert count_after == 2

    @pytest.mark.asyncio
    async def test_get_unread_count_excludes_other_tenants(self, mock_db_session):
        """get_unread_count for tenant_id=1 ignores notifications owned by tenant_id=2."""
        svc = NotificationService(mock_db_session)

        # Send two notifications for tenant_id=1
        for i in range(2):
            await svc.send_notification(
                user_id=1,
                notification_type="email",
                title=f"T1 Notification {i+1}",
                content="Test",
                tenant_id=1,
            )

        # Seed a user in tenant_id=2 so the user-exists check passes for that tenant
        mock_db_session._state.users[2] = {
            "id": 2,
            "tenant_id": 2,
            "username": "t2user",
            "email": "t2@example.com",
            "role": "user",
            "status": "active",
            "full_name": "Tenant 2 User",
            "bio": None,
            "created_at": None,
            "updated_at": None,
        }
        # Send three notifications for tenant_id=2
        for i in range(3):
            await svc.send_notification(
                user_id=2,
                notification_type="email",
                title=f"T2 Notification {i+1}",
                content="Test",
                tenant_id=2,
            )

        # Tenant 1 sees only its own 2 unread
        count_t1 = await svc.get_unread_count(user_id=1, tenant_id=1)
        assert count_t1 == 2

        # Tenant 2 sees only its own 3 unread
        count_t2 = await svc.get_unread_count(user_id=2, tenant_id=2)
        assert count_t2 == 3

    @pytest.mark.asyncio
    async def test_mark_as_read_nonexistent_raises_not_found(self, mock_db_session):
        """mark_as_read with a non-existent notification_id raises NotFoundException."""
        svc = NotificationService(mock_db_session)
        with pytest.raises(NotFoundException):
            await svc.mark_as_read(notification_id=9999, tenant_id=1)

    @pytest.mark.asyncio
    async def test_mark_as_read_wrong_tenant_raises_not_found(self, mock_db_session):
        """mark_as_read with the wrong tenant_id raises NotFoundException."""
        svc = NotificationService(mock_db_session)
        created = await svc.send_notification(
            user_id=1,
            notification_type="email",
            title="Tenant 1 notification",
            content="Test",
            tenant_id=1,
        )
        with pytest.raises(NotFoundException):
            await svc.mark_as_read(notification_id=created.id, tenant_id=2)

    @pytest.mark.asyncio
    async def test_mark_as_read_already_read_is_idempotent(self, mock_db_session):
        """mark_as_read on an already-read notification is a no-op (no error)."""
        svc = NotificationService(mock_db_session)
        created = await svc.send_notification(
            user_id=1,
            notification_type="email",
            title="Read me",
            content="Test",
            tenant_id=1,
        )
        await svc.mark_as_read(notification_id=created.id, tenant_id=1)
        # Second call should not raise — the service treats already-read as a no-op
        result = await svc.mark_as_read(notification_id=created.id, tenant_id=1)
        assert result.read_at is not None
