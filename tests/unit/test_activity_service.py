"""Unit tests for ActivityService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.activity import ActivityType
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.activity_service import ActivityService


class MockActivityModel:
    """Simulates an ActivityModel row."""

    def __init__(
        self,
        id: int | None = None,
        tenant_id: int = 0,
        customer_id: int = 1,
        opportunity_id: int | None = None,
        type: str = "call",
        content: str = "Test content",
        created_by: int = 1,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.tenant_id = tenant_id
        self.customer_id = customer_id
        self.opportunity_id = opportunity_id
        self.type = type
        self.content = content
        self.created_by = created_by
        self.created_at = created_at or datetime.now(UTC)

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "opportunity_id": self.opportunity_id,
            "type": self.type,
            "content": self.content,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class MockResult:
    """Simulates a SQLAlchemy Result object."""

    def __init__(self, rows=None, total=None):
        self._rows = rows or []
        self._total = total

    def scalar_one_or_none(self):
        if self._total is not None:
            return self._total
        return self._rows[0] if self._rows else None

    def scalar(self):
        if self._total is not None:
            return self._total
        if not self._rows:
            return None
        first = self._rows[0]
        if isinstance(first, (list, tuple)):
            return first[0]
        return first

    def scalars(self):
        return MagicMock(all=MagicMock(return_value=self._rows))

    def __iter__(self):
        return iter(self._rows)


@pytest.fixture
def mock_db_session():
    """Build a mock session whose execute() is driven by side_effect list."""
    session = MagicMock(spec=["execute", "add", "flush", "refresh"])
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def activity_service(mock_db_session):
    """Return a fresh ActivityService per test."""
    return ActivityService(mock_db_session)


class TestCreateActivity:
    """Tests for ActivityService.create_activity."""

    @pytest.mark.asyncio
    async def test_create_activity_returns_activity(self, activity_service, mock_db_session):
        """create_activity returns an Activity domain object after refresh."""

        async def mock_refresh(model):
            model.id = 1

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        mock_db_session.execute.side_effect = [
            MockResult([]),  # refresh triggers a select via _fetch -> scalar_one_or_none returns None
        ]

        result = await activity_service.create_activity(
            customer_id=1,
            activity_type="call",
            content="Test content",
            created_by=1,
            tenant_id=1,
        )

        assert result.id == 1
        assert result.content == "Test content"
        assert result.type == ActivityType.CALL
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_activity_invalid_type_raises(self, activity_service, mock_db_session):
        """create_activity raises ValidationException for unknown activity_type."""
        mock_db_session.execute.side_effect = []
        with pytest.raises(ValidationException, match="无效的活动类型"):
            await activity_service.create_activity(
                customer_id=1,
                activity_type="invalid",
                content="Test",
                created_by=1,
                tenant_id=1,
            )


class TestGetActivity:
    """Tests for ActivityService.get_activity."""

    @pytest.mark.asyncio
    async def test_get_activity_found(self, activity_service, mock_db_session):
        """get_activity returns an Activity when the record exists."""
        row1 = MockActivityModel(
            id=1,
            tenant_id=1,
            customer_id=1,
            type="call",
            content="Test content",
            created_by=1,
        )

        mock_db_session.execute.side_effect = [MockResult([row1])]

        result = await activity_service.get_activity(activity_id=1, tenant_id=1)

        assert result.content == "Test content"
        assert result.type == ActivityType.CALL

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, activity_service, mock_db_session):
        """get_activity raises NotFoundException when the record does not exist."""
        mock_db_session.execute.side_effect = [MockResult([])]

        with pytest.raises(NotFoundException, match="活动记录"):
            await activity_service.get_activity(activity_id=999, tenant_id=1)


class TestUpdateActivity:
    """Tests for ActivityService.update_activity."""

    @pytest.mark.asyncio
    async def test_update_activity(self, activity_service, mock_db_session):
        """update_activity returns the updated Activity."""
        row1 = MockActivityModel(
            id=1,
            tenant_id=1,
            customer_id=1,
            type="call",
            content="Original content",
            created_by=1,
        )
        row1_updated = MockActivityModel(
            id=1,
            tenant_id=1,
            customer_id=1,
            type="call",
            content="Updated",
            created_by=1,
        )

        mock_db_session.execute.side_effect = [
            MockResult([row1]),  # _fetch before update
            MockResult([]),  # update statement (delete returns empty for scalars)
            MockResult([row1_updated]),  # _fetch after update
        ]

        result = await activity_service.update_activity(
            activity_id=1,
            tenant_id=1,
            content="Updated",
        )

        assert result.content == "Updated"


class TestDeleteActivity:
    """Tests for ActivityService.delete_activity."""

    @pytest.mark.asyncio
    async def test_delete_activity(self, activity_service, mock_db_session):
        """delete_activity returns {"id": int} and subsequent get_activity raises."""
        row1 = MockActivityModel(
            id=1,
            tenant_id=1,
            customer_id=1,
            type="call",
            content="To be deleted",
            created_by=1,
        )

        mock_db_session.execute.side_effect = [
            MockResult([row1]),  # _fetch before delete
            MockResult([]),  # delete statement
        ]

        result = await activity_service.delete_activity(activity_id=1, tenant_id=1)

        assert result == {"id": 1}

        # Subsequent get_activity raises NotFoundException
        mock_db_session.execute.side_effect = [MockResult([])]
        with pytest.raises(NotFoundException, match="活动记录"):
            await activity_service.get_activity(activity_id=1, tenant_id=1)


class TestListActivities:
    """Tests for ActivityService.list_activities."""

    @pytest.mark.asyncio
    async def test_list_activities_pagination(self, activity_service, mock_db_session):
        """list_activities returns paginated items and total count."""
        row1 = MockActivityModel(
            id=1,
            tenant_id=1,
            customer_id=1,
            type="call",
            content="Call 1",
            created_by=1,
        )
        row2 = MockActivityModel(
            id=2,
            tenant_id=1,
            customer_id=1,
            type="email",
            content="Email 1",
            created_by=1,
        )

        mock_db_session.execute.side_effect = [
            MockResult([], total=3),  # count query
            MockResult([row1, row2]),  # select query
        ]

        items, total = await activity_service.list_activities(tenant_id=1, page=1, page_size=2)

        assert len(items) == 2
        assert total == 3
