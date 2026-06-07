"""
Unit tests for Analytics ORM models.
"""
import pytest
from datetime import datetime

from db.models.analytics import (
    ChartDataModel,
    ChartType,
    DashboardModel,
    ReportModel,
    ReportType,
)


class TestDashboardModel:
    """Tests for DashboardModel."""

    def test_to_dict_keys(self):
        """to_dict() returns all expected keys."""
        dashboard = DashboardModel(
            id=1,
            tenant_id=1,
            name="Sales Overview",
            description="Q1 sales metrics",
            widgets=[],
            owner_id=42,
            is_default=False,
        )
        result = dashboard.to_dict()
        assert "id" in result
        assert "tenant_id" in result
        assert "name" in result
        assert "description" in result
        assert "widgets" in result
        assert "owner_id" in result
        assert "is_default" in result
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_values(self):
        """to_dict() returns correct values."""
        dashboard = DashboardModel(
            id=1,
            tenant_id=1,
            name="Sales Overview",
            description="Q1 sales metrics",
            widgets=[{"type": "chart", "config": {"chartType": "bar"}}],
            owner_id=42,
            is_default=False,
        )
        result = dashboard.to_dict()
        assert result["id"] == 1
        assert result["tenant_id"] == 1
        assert result["name"] == "Sales Overview"
        assert result["description"] == "Q1 sales metrics"
        assert result["widgets"] == [{"type": "chart", "config": {"chartType": "bar"}}]
        assert result["owner_id"] == 42
        assert result["is_default"] is False

    def test_created_at_isoformat(self):
        """created_at is formatted as ISO string."""
        now = datetime(2026, 1, 15, 10, 30, 0)
        dashboard = DashboardModel(
            id=1,
            tenant_id=1,
            name="Test",
            description=None,
            widgets=[],
            owner_id=1,
            is_default=False,
        )
        dashboard.created_at = now
        dashboard.updated_at = now
        result = dashboard.to_dict()
        assert result["created_at"] == "2026-01-15T10:30:00"
        assert result["updated_at"] == "2026-01-15T10:30:00"


class TestReportModel:
    """Tests for ReportModel."""

    def test_to_dict_keys(self):
        """to_dict() returns all expected keys."""
        report = ReportModel(
            id=1,
            tenant_id=1,
            name="Monthly Revenue",
            type="sales_revenue",
            config={},
            date_range={},
            created_by=5,
        )
        result = report.to_dict()
        assert "id" in result
        assert "tenant_id" in result
        assert "name" in result
        assert "type" in result
        assert "config" in result
        assert "date_range" in result
        assert "created_by" in result
        assert "last_run_at" in result
        assert "created_at" in result

    def test_to_dict_type_value(self):
        """to_dict()["type"] matches the input value."""
        report = ReportModel(
            id=1,
            tenant_id=1,
            name="Monthly Revenue",
            type="sales_revenue",
            config={},
            date_range={},
            created_by=5,
        )
        result = report.to_dict()
        assert result["type"] == "sales_revenue"

    def test_to_dict_config(self):
        """config field is included correctly."""
        config = {"orientation": "portrait", "filters": ["region=US"]}
        report = ReportModel(
            id=1,
            tenant_id=1,
            name="Test Report",
            type="customer_growth",
            config=config,
            date_range={},
            created_by=5,
        )
        result = report.to_dict()
        assert result["config"] == config


class TestChartDataModel:
    """Tests for ChartDataModel."""

    def test_to_dict_keys(self):
        """to_dict() returns all expected keys."""
        chart = ChartDataModel(
            id=1,
            report_id=10,
            chart_type="bar",
            data={},
        )
        result = chart.to_dict()
        assert "id" in result
        assert "report_id" in result
        assert "chart_type" in result
        assert "data" in result
        assert "created_at" in result

    def test_to_dict_chart_type(self):
        """to_dict()["chart_type"] matches the input value."""
        chart = ChartDataModel(
            id=1,
            report_id=10,
            chart_type="bar",
            data={"labels": ["Jan"], "datasets": []},
        )
        result = chart.to_dict()
        assert result["chart_type"] == "bar"

    def test_to_dict_data(self):
        """to_dict()["data"] matches the input dict."""
        data = {"labels": ["Jan", "Feb"], "datasets": [{"label": "Revenue", "data": [100, 200]}]}
        chart = ChartDataModel(
            id=1,
            report_id=10,
            chart_type="line",
            data=data,
        )
        result = chart.to_dict()
        assert result["data"] == data

    def test_to_dict_report_id(self):
        """to_dict()["report_id"] matches the input value."""
        chart = ChartDataModel(
            id=1,
            report_id=42,
            chart_type="pie",
            data={},
        )
        result = chart.to_dict()
        assert result["report_id"] == 42


class TestEnumValues:
    """Tests for SQLAlchemy Enum values (exposed via the .enums attribute)."""

    def test_report_type_values(self):
        """ReportType contains all expected string values."""
        assert "sales_revenue" in ReportType.enums
        assert "sales_conversion" in ReportType.enums
        assert "customer_growth" in ReportType.enums
        assert "customer_churn" in ReportType.enums
        assert "pipeline_forecast" in ReportType.enums
        assert "team_performance" in ReportType.enums

    def test_chart_type_values(self):
        """ChartType contains all expected string values."""
        assert "line" in ChartType.enums
        assert "bar" in ChartType.enums
        assert "pie" in ChartType.enums
        assert "funnel" in ChartType.enums
        assert "table" in ChartType.enums

    def test_report_type_count(self):
        """ReportType has exactly 6 values."""
        assert len(ReportType.enums) == 6

    def test_chart_type_count(self):
        """ChartType has exactly 5 values."""
        assert len(ChartType.enums) == 5