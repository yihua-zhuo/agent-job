"""Unit tests for AnalyticsService."""
import pytest
from services.analytics_service import AnalyticsService
from pkg.errors.app_exceptions import NotFoundException
from tests.unit.conftest import make_mock_session


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
def analytics_service(mock_db_session):
    return AnalyticsService(mock_db_session)


class TestAnalyticsService:

    def test_get_dashboard_not_found(self, analytics_service):
        with pytest.raises(NotFoundException):
            analytics_service.get_dashboard(9999)
