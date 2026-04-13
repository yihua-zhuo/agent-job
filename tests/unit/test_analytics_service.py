"""Unit tests for AnalyticsService."""
import pytest
from src.services.analytics_service import AnalyticsService


@pytest.fixture
def analytics_service():
    """Create a fresh AnalyticsService instance for each test."""
    return AnalyticsService()


class TestAnalyticsService:
    """Tests for AnalyticsService."""

    def test_get_sales_revenue_report_returns_dict(self, analytics_service):
        """Test get_sales_revenue_report returns a dict with chart fields."""
        result = analytics_service.get_sales_revenue_report('2024-01-01', '2024-12-31')
        assert isinstance(result, dict)
        assert 'labels' in result
        assert 'datasets' in result

    def test_get_sales_conversion_report_returns_dict(self, analytics_service):
        """Test get_sales_conversion_report returns a dict with chart fields."""
        result = analytics_service.get_sales_conversion_report('2024-01-01', '2024-12-31')
        assert isinstance(result, dict)
        assert 'labels' in result
        assert 'datasets' in result

    def test_get_customer_growth_report_returns_dict(self, analytics_service):
        """Test get_customer_growth_report returns a dict."""
        result = analytics_service.get_customer_growth_report('2024-01-01', '2024-12-31')
        assert isinstance(result, dict)

    def test_get_pipeline_forecast_returns_dict(self, analytics_service):
        """Test get_pipeline_forecast returns a dict."""
        result = analytics_service.get_pipeline_forecast(1)
        assert isinstance(result, dict)

    def test_get_team_performance_returns_dict(self, analytics_service):
        """Test get_team_performance returns a dict."""
        result = analytics_service.get_team_performance('2024-01-01', '2024-12-31')
        assert isinstance(result, dict)

    def test_create_dashboard_success(self, analytics_service):
        """Test create_dashboard returns success with correct name."""
        result = analytics_service.create_dashboard('Sales DB', owner_id=1, description='Test')
        assert bool(result) is True
        assert result.data['name'] == 'Sales DB'

    def test_get_dashboard_found(self, analytics_service):
        """Test get_dashboard returns the dashboard when it exists."""
        create = analytics_service.create_dashboard('Dashboard A', owner_id=1)
        dashboard_id = create.data['id']
        retrieved = analytics_service.get_dashboard(dashboard_id)
        assert bool(retrieved) is True
        assert retrieved.data['name'] == 'Dashboard A'

    def test_get_dashboard_not_found(self, analytics_service):
        """Test get_dashboard returns error for nonexistent dashboard."""
        result = analytics_service.get_dashboard(9999)
        assert bool(result) is False

    def test_list_dashboards_pagination(self, analytics_service):
        """Test list_dashboards returns paginated dashboards."""
        analytics_service.create_dashboard('DB 1', owner_id=1)
        analytics_service.create_dashboard('DB 2', owner_id=1)
        result = analytics_service.list_dashboards(owner_id=1)
        assert bool(result) is True
        assert result.data.total >= 2