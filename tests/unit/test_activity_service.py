"""Unit tests for src/services/activity_service.py."""

from datetime import datetime

import pytest

from models.activity import ActivityType
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.activity_service import ActivityService
from tests.unit.conftest import MockState, make_activity_handler, make_mock_session


@pytest.fixture
def activity_state():
    return MockState()


@pytest.fixture
def mock_db_session(activity_state):
    session = make_mock_session([make_activity_handler(activity_state)], state=activity_state)

    async def refresh_side_effect(obj):
        if obj.id is None:
            obj.id = activity_state.activities_next_id

    session.refresh.side_effect = refresh_side_effect
    return session


@pytest.fixture
def activity_service(mock_db_session):
    return ActivityService(mock_db_session)


def add_activity(
    state: MockState,
    *,
    activity_id: int = 1,
    tenant_id: int = 1,
    customer_id: int = 1,
    activity_type: str = "call",
    content: str = "Test call",
    created_at: datetime | None = None,
):
    record = {
        "id": activity_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "opportunity_id": None,
        "type": activity_type,
        "content": content,
        "created_by": 1,
        "created_at": created_at or datetime.utcnow(),
    }
    state.activities[activity_id] = record
    state.activities_next_id = max(state.activities_next_id, activity_id + 1)
    return record


class TestCreateActivity:
    """Tests for ActivityService.create_activity."""

    @pytest.mark.asyncio
    async def test_create_activity_returns_activity(self, mock_db_session):
        """create_activity returns an Activity with correct fields."""
        service = ActivityService(mock_db_session)

        result = await service.create_activity(
            customer_id=1,
            activity_type="call",
            content="Test call",
            created_by=1,
            tenant_id=1,
        )

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        assert result.content == "Test call"
        assert result.type == ActivityType.CALL
        assert result.id == 1
        assert result.tenant_id == 1

    @pytest.mark.asyncio
    async def test_create_activity_rejects_invalid_type(self, activity_service):
        """create_activity raises ValidationException for invalid activity_type."""
        with pytest.raises(ValidationException):
            await activity_service.create_activity(
                customer_id=1,
                activity_type="invalid",
                content="Bad type",
                created_by=1,
                tenant_id=1,
            )


class TestGetActivity:
    """Tests for ActivityService.get_activity."""

    @pytest.mark.asyncio
    async def test_get_activity_found(self, activity_service, activity_state):
        """get_activity returns the activity when tenant and id match."""
        add_activity(activity_state, activity_id=1, tenant_id=1)

        result = await activity_service.get_activity(activity_id=1, tenant_id=1)

        assert result.content == "Test call"
        assert result.type == ActivityType.CALL
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, activity_service):
        """get_activity raises NotFoundException when activity does not exist."""
        with pytest.raises(NotFoundException):
            await activity_service.get_activity(activity_id=9999, tenant_id=1)

    @pytest.mark.asyncio
    async def test_get_activity_rejects_wrong_tenant(self, activity_service, activity_state):
        """get_activity does not return another tenant's activity."""
        add_activity(activity_state, activity_id=1, tenant_id=2)

        with pytest.raises(NotFoundException):
            await activity_service.get_activity(activity_id=1, tenant_id=1)


class TestUpdateActivity:
    """Tests for ActivityService.update_activity."""

    @pytest.mark.asyncio
    async def test_update_activity(self, activity_service, activity_state):
        """update_activity returns the activity with updated content."""
        add_activity(activity_state, activity_id=1, tenant_id=1, content="Original content")

        result = await activity_service.update_activity(activity_id=1, tenant_id=1, content="Updated content")

        assert result.content == "Updated content"
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_activity_with_no_fields_only_refetches(self, activity_service, activity_state, mock_db_session):
        """update_activity with no fields skips UPDATE and returns current activity."""
        add_activity(activity_state, activity_id=1, tenant_id=1, content="Unchanged")

        result = await activity_service.update_activity(activity_id=1, tenant_id=1)

        assert result.content == "Unchanged"
        assert mock_db_session.execute.await_count == 2
        mock_db_session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_activity_rejects_invalid_type(self, activity_service, activity_state):
        """update_activity raises ValidationException for invalid activity_type."""
        add_activity(activity_state, activity_id=1, tenant_id=1)

        with pytest.raises(ValidationException):
            await activity_service.update_activity(activity_id=1, tenant_id=1, activity_type="invalid")

    @pytest.mark.asyncio
    async def test_update_activity_rejects_wrong_tenant(self, activity_service, activity_state):
        """update_activity does not update another tenant's activity."""
        add_activity(activity_state, activity_id=1, tenant_id=2, content="Original")

        with pytest.raises(NotFoundException):
            await activity_service.update_activity(activity_id=1, tenant_id=1, content="Updated")

        assert activity_state.activities[1]["content"] == "Original"


class TestDeleteActivity:
    """Tests for ActivityService.delete_activity."""

    @pytest.mark.asyncio
    async def test_delete_activity(self, activity_service, activity_state):
        """delete_activity removes the activity and returns id dict."""
        add_activity(activity_state, activity_id=1, tenant_id=1)

        result = await activity_service.delete_activity(activity_id=1, tenant_id=1)

        assert result == {"id": 1}
        assert 1 not in activity_state.activities

        with pytest.raises(NotFoundException):
            await activity_service.get_activity(activity_id=1, tenant_id=1)

    @pytest.mark.asyncio
    async def test_delete_activity_rejects_wrong_tenant(self, activity_service, activity_state):
        """delete_activity does not remove another tenant's activity."""
        add_activity(activity_state, activity_id=1, tenant_id=2)

        with pytest.raises(NotFoundException):
            await activity_service.delete_activity(activity_id=1, tenant_id=1)

        assert 1 in activity_state.activities


class TestListActivitiesPagination:
    """Tests for ActivityService.list_activities pagination and filters."""

    @pytest.mark.asyncio
    async def test_list_activities_pagination(self, activity_service, activity_state):
        """list_activities returns paginated items and correct total."""
        add_activity(activity_state, activity_id=1, tenant_id=1, activity_type="call", content="Call 1",
                      created_at=datetime(2025, 1, 1, 10, 0))
        add_activity(activity_state, activity_id=2, tenant_id=1, activity_type="email", content="Email 1",
                      created_at=datetime(2025, 1, 1, 11, 0))
        add_activity(activity_state, activity_id=3, tenant_id=1, activity_type="meeting", content="Meeting 1",
                      created_at=datetime(2025, 1, 1, 12, 0))
        add_activity(activity_state, activity_id=4, tenant_id=2, activity_type="call", content="Other tenant",
                      created_at=datetime(2025, 1, 1, 13, 0))

        items, total = await activity_service.list_activities(tenant_id=1, page=1, page_size=2)

        assert len(items) == 2
        assert total == 3
        assert {item.id for item in items} == {2, 3}

    @pytest.mark.asyncio
    async def test_list_activities_filters_customer_and_type(self, activity_service, activity_state):
        """list_activities supports customer_id and activity_type filters."""
        add_activity(activity_state, activity_id=1, tenant_id=1, customer_id=1, activity_type="call")
        add_activity(activity_state, activity_id=2, tenant_id=1, customer_id=1, activity_type="email")
        add_activity(activity_state, activity_id=3, tenant_id=1, customer_id=2, activity_type="call")

        items, total = await activity_service.list_activities(
            tenant_id=1,
            customer_id=1,
            activity_type="call",
        )

        assert total == 1
        assert [item.id for item in items] == [1]
