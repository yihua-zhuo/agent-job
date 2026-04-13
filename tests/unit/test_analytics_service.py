"""Unit tests for AnalyticsService."""
import pytest
from services.analytics_service import AnalyticsService


@pytest.fixture
def analytics_service():
    return AnalyticsService()


@pytest.mark.asyncio
class TestAnalyticsService:
    async def test_get_sales_revenue_report_returns_dict(self, analytics_service):
        result = await analytics_service.get_sales_revenue_report("2024-01-01", "2024-12-31")
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result

    async def test_get_sales_conversion_report_returns_dict(self, analytics_service):
        result = await analytics_service.get_sales_conversion_report("2024-01-01", "2024-12-31")
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result

    async def test_get_customer_growth_report_returns_dict(self, analytics_service):
        result = await analytics_service.get_customer_growth_report("2024-01-01", "2024-12-31")
        assert isinstance(result, dict)

    async def test_get_pipeline_forecast_returns_dict(self, analytics_service):
        result = await analytics_service.get_pipeline_forecast(1)
        assert isinstance(result, dict)

    async def test_get_team_performance_returns_dict(self, analytics_service):
        result = await analytics_service.get_team_performance("2024-01-01", "2024-12-31")
        assert isinstance(result, dict)

    async def test_create_dashboard_success(self, analytics_service):
        result = await analytics_service.create_dashboard("Sales DB", owner_id=1, description="Test")
        assert bool(result) is True
        assert result.data["name"] == "Sales DB"

    async def test_get_dashboard_found(self, analytics_service):
        create = await analytics_service.create_dashboard("Dashboard A", owner_id=1)
        dashboard_id = create.data["id"]
        retrieved = await analytics_service.get_dashboard(dashboard_id)
        assert bool(retrieved) is True
        assert retrieved.data["name"] == "Dashboard A"

    async def test_get_dashboard_not_found(self, analytics_service):
        result = await analytics_service.get_dashboard(9999)
        assert bool(result) is False

    async def test_list_dashboards_pagination(self, analytics_service):
        await analytics_service.create_dashboard("DB 1", owner_id=1)
        await analytics_service.create_dashboard("DB 2", owner_id=1)
        result = await analytics_service.list_dashboards(owner_id=1)
        assert bool(result) is True
        assert result.data.total >= 2
