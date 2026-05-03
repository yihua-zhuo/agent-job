"""Unit tests for AnalyticsService."""
import pytest
from services.analytics_service import AnalyticsService


@pytest.fixture
def analytics_service(mock_db_session):
    return AnalyticsService(mock_db_session)


class TestAnalyticsService:

    def test_get_dashboard_not_found(self, analytics_service):
        result = analytics_service.get_dashboard(9999)
        assert result is None