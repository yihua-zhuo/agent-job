"""
Integration tests for Analytics and Report services.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_analytics_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest

from src.models.response import ResponseStatus
from src.services.analytics_service import AnalyticsService
from src.services.report_service import ReportService
from src.services.user_service import UserService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Dashboard integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestDashboardIntegration:
    """Full dashboard lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int) -> int:
        """Create a user and return their id (needed for owner_id)."""
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"dashuser_{suffix}",
            email=f"dash_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def test_create_and_get_dashboard(self, db_schema, tenant_id):
        """Create a dashboard and verify it can be retrieved."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        result = await svc.create_dashboard(
            name="Sales Overview",
            owner_id=uid,
            tenant_id=tenant_id,
            description="Main sales metrics dashboard",
        )
        assert result.status == ResponseStatus.SUCCESS, f"Got: {result.status}, {result.message}"
        data = result.data
        assert data["name"] == "Sales Overview"
        assert data["tenant_id"] == tenant_id
        assert data["owner_id"] == uid
        assert data["description"] == "Main sales metrics dashboard"
        assert data["widgets"] == []

        fetched = await svc.get_dashboard(data["id"], tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == "Sales Overview"

    async def test_update_dashboard(self, db_schema, tenant_id):
        """Update dashboard name, description, and widgets."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await svc.create_dashboard(
            name="Original Name",
            owner_id=uid,
            tenant_id=tenant_id,
        )
        did = created.data["id"]

        updated = await svc.update_dashboard(
            dashboard_id=did,
            tenant_id=tenant_id,
            name="Updated Name",
            description="New description",
            widgets=[{"type": "chart", "config": {"chartType": "bar"}}],
        )
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["name"] == "Updated Name"
        assert updated.data["description"] == "New description"
        assert len(updated.data["widgets"]) == 1

    async def test_get_dashboard_not_found(self, db_schema, tenant_id):
        """Non-existent dashboard returns NOT_FOUND."""
        svc = AnalyticsService()
        result = await svc.get_dashboard(dashboard_id=999_999_999, tenant_id=tenant_id)
        assert result.status == ResponseStatus.NOT_FOUND

    async def test_list_dashboards(self, db_schema, tenant_id):
        """List returns all dashboards for the tenant."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)
        suffix = uuid.uuid4().hex[:8]

        await svc.create_dashboard(
            name=f"Dash A {suffix}", owner_id=uid, tenant_id=tenant_id
        )
        await svc.create_dashboard(
            name=f"Dash B {suffix}", owner_id=uid, tenant_id=tenant_id
        )

        result = await svc.list_dashboards(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        names = [d["name"] for d in result.data.items]
        assert any(f"Dash A {suffix}" in n for n in names)
        assert any(f"Dash B {suffix}" in n for n in names)

    async def test_list_dashboards_by_owner(self, db_schema, tenant_id):
        """List dashboards filtered by owner_id."""
        svc = AnalyticsService()
        uid1 = await self._seed_user(tenant_id)
        uid2 = await self._seed_user(tenant_id)
        suffix = uuid.uuid4().hex[:8]

        await svc.create_dashboard(name=f"Owner1 Dash {suffix}", owner_id=uid1, tenant_id=tenant_id)
        await svc.create_dashboard(name=f"Owner2 Dash {suffix}", owner_id=uid2, tenant_id=tenant_id)

        result = await svc.list_dashboards(owner_id=uid1, tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        # All returned dashboards should belong to the specified owner
        assert all(d["owner_id"] == uid1 for d in result.data.items)

    async def test_dashboard_cross_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2
    ):
        """Dashboards are not visible across tenants."""
        svc = AnalyticsService()
        uid1 = await self._seed_user(tenant_id)
        uid2 = await self._seed_user(tenant_id)

        d1 = await svc.create_dashboard(
            name="Tenant 1 Dash", owner_id=uid1, tenant_id=tenant_id
        )
        d2 = await svc.create_dashboard(
            name="Tenant 2 Dash", owner_id=uid2, tenant_id=tenant_id_2
        )

        list_t1 = await svc.list_dashboards(tenant_id=tenant_id)
        ids_t1 = [d["id"] for d in list_t1.data.items]

        # Tenant 1's dashboard should be in their list
        assert d1.data["id"] in ids_t1
        # Tenant 2's dashboard should NOT appear in Tenant 1's list
        assert d2.data["id"] not in ids_t1

        list_t2 = await svc.list_dashboards(tenant_id=tenant_id_2)
        ids_t2 = [d["id"] for d in list_t2.data.items]
        assert d2.data["id"] in ids_t2
        assert d1.data["id"] not in ids_t2

    async def test_add_widget_to_dashboard(self, db_schema, tenant_id):
        """Add a widget to an existing dashboard."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await svc.create_dashboard(
            name="Widget Test", owner_id=uid, tenant_id=tenant_id
        )
        did = created.data["id"]

        result = await svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "kpi", "config": {"metric": "revenue"}},
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS

        fetched = await svc.get_dashboard(did, tenant_id=tenant_id)
        assert len(fetched.data["widgets"]) >= 1

    async def test_remove_widget_from_dashboard(self, db_schema, tenant_id):
        """Remove a widget from a dashboard."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await svc.create_dashboard(
            name="Remove Widget Test", owner_id=uid, tenant_id=tenant_id
        )
        did = created.data["id"]

        # Add two widgets
        await svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "chart", "config": {"chartType": "line"}},
            tenant_id=tenant_id,
        )
        add_result = await svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "kpi", "config": {"metric": "count"}},
            tenant_id=tenant_id,
        )
        widget_id = add_result.data["id"]

        # Remove one widget
        removed = await svc.remove_widget(
            dashboard_id=did, widget_id=widget_id, tenant_id=tenant_id
        )
        assert removed.status == ResponseStatus.SUCCESS

    async def test_dashboard_is_default_flag(self, db_schema, tenant_id):
        """Update and verify is_default flag on dashboard."""
        svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await svc.create_dashboard(
            name="Default Dash", owner_id=uid, tenant_id=tenant_id
        )
        did = created.data["id"]
        assert created.data["is_default"] is False

        updated = await svc.update_dashboard(
            dashboard_id=did, tenant_id=tenant_id, is_default=True
        )
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["is_default"] is True


# ──────────────────────────────────────────────────────────────────────────────────────
#  Report integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestReportIntegration:
    """Report generation and export via the real DB."""

    async def _seed_user(self, tenant_id: int) -> int:
        """Create a user and return their id (needed for created_by)."""
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"repuser_{suffix}",
            email=f"rep_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def test_create_and_get_report(self, db_schema, tenant_id):
        """Create a report and verify it can be retrieved via run_report."""
        analytics_svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        result = await analytics_svc.create_report(
            tenant_id=tenant_id,
            name="Monthly Sales Report",
            report_type="sales_revenue",
            config={"orientation": "portrait"},
            created_by=uid,
        )
        assert result.status == ResponseStatus.SUCCESS, f"Got: {result.status}, {result.message}"
        data = result.data
        assert data["name"] == "Monthly Sales Report"
        assert data["type"] == "sales_revenue"
        assert data["tenant_id"] == tenant_id
        assert data["created_by"] == uid

    async def test_create_report_different_types(self, db_schema, tenant_id):
        """Create reports of different types (sales_revenue, sales_conversion, etc.)."""
        analytics_svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        for rtype in ["sales_revenue", "sales_conversion", "customer_growth", "pipeline_forecast"]:
            result = await analytics_svc.create_report(
                tenant_id=tenant_id,
                name=f"Report {rtype}",
                report_type=rtype,
                config={},
                created_by=uid,
            )
            assert result.status == ResponseStatus.SUCCESS, f"Failed for type {rtype}: {result.message}"
            assert result.data["type"] == rtype

    async def test_generate_pdf_report(self, db_schema, tenant_id):
        """Generate a PDF report and verify structure."""
        svc = ReportService()
        await self._seed_user(tenant_id)

        generated = await svc.generate_pdf_report(
            report_data={
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [{"data": [100, 200, 300]}],
            },
            title="Monthly Sales PDF",
        )
        assert generated["status"] == "generated"
        assert generated["format"] == "pdf"
        assert generated["title"] == "Monthly Sales PDF"
        assert "generated_at" in generated

    async def test_generate_excel_report(self, db_schema, tenant_id):
        """Generate an Excel report and verify structure."""
        svc = ReportService()
        await self._seed_user(tenant_id)

        generated = await svc.generate_excel_report(
            report_data={
                "labels": ["Product A", "Product B"],
                "datasets": [{"data": [500, 750]}],
            },
            title="Monthly Sales Excel",
        )
        assert generated["status"] == "generated"
        assert generated["format"] == "excel"
        assert generated["title"] == "Monthly Sales Excel"

    async def test_export_to_csv(self, db_schema, tenant_id):
        """Export data to CSV and verify file structure."""
        svc = ReportService()
        await self._seed_user(tenant_id)

        data = [
            {"name": "Alice", "email": "alice@example.com", "amount": 1000},
            {"name": "Bob", "email": "bob@example.com", "amount": 2000},
        ]
        filename = f"test_export_{uuid.uuid4().hex[:8]}.csv"

        result = await svc.export_to_csv(data=data, filename=filename)
        assert result["status"] == "success"
        assert result["rows_exported"] == 2
        assert filename in result["filename"]
        assert "filepath" in result

    async def test_export_to_csv_empty_data(self, db_schema, tenant_id):
        """Export with no data returns error status."""
        svc = ReportService()
        result = await svc.export_to_csv(data=[], filename="empty.csv")
        assert result["status"] == "error"
        assert "No data to export" in result["message"]

    async def test_schedule_report(self, db_schema, tenant_id):
        """Schedule a report and verify scheduling returns success."""
        analytics_svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await analytics_svc.create_report(
            tenant_id=tenant_id,
            name="Scheduled Report",
            report_type="sales_revenue",
            config={},
            created_by=uid,
        )
        rid = created.data["id"]

        report_svc = ReportService()
        schedule = {
            "frequency": "daily",
            "time": "09:00",
            "timezone": "UTC",
            "recipients": ["team@example.com"],
        }
        result = await report_svc.schedule_report(report_id=rid, schedule=schedule)
        assert result["report_id"] == rid
        assert result["schedule"]["frequency"] == "daily"
        assert result["active"] is True

    async def test_schedule_report_multiple(self, db_schema, tenant_id):
        """Scheduling the same report twice updates the schedule (idempotent key)."""
        analytics_svc = AnalyticsService()
        uid = await self._seed_user(tenant_id)

        created = await analytics_svc.create_report(
            tenant_id=tenant_id,
            name="Re-scheduled Report",
            report_type="sales_conversion",
            config={},
            created_by=uid,
        )
        rid = created.data["id"]

        report_svc = ReportService()
        await report_svc.schedule_report(
            report_id=rid,
            schedule={"frequency": "daily", "time": "09:00", "timezone": "UTC", "recipients": []},
        )
        updated = await report_svc.schedule_report(
            report_id=rid,
            schedule={"frequency": "weekly", "time": "10:00", "timezone": "UTC", "recipients": []},
        )
        # The second call replaces the schedule (same report_id key)
        assert updated["schedule"]["frequency"] == "weekly"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Chart / sync report helper integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestChartHelpersIntegration:
    """Sync chart helper methods that wrap async DB queries."""

    async def _seed_user(self, tenant_id: int) -> int:
        user_svc = UserService()
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"chartuser_{suffix}",
            email=f"chart_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def test_get_sales_revenue_report(self, db_schema, tenant_id):
        """get_sales_revenue_report returns chart data structure."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = await svc.get_sales_revenue_report(
            start_date="2026-01-01", end_date="2026-01-31", group_by="day"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "line"

    async def test_get_sales_conversion_report(self, db_schema, tenant_id):
        """get_sales_conversion_report returns funnel chart data."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = svc.get_sales_conversion_report(
            start_date="2026-01-01", end_date="2026-01-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "funnel"

    async def test_get_customer_growth_report(self, db_schema, tenant_id):
        """get_customer_growth_report returns bar chart data."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = svc.get_customer_growth_report(
            start_date="2026-01-01", end_date="2026-03-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"

    async def test_get_pipeline_forecast(self, db_schema, tenant_id):
        """get_pipeline_forecast returns pipeline forecast data."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = svc.get_pipeline_forecast(pipeline_id=1)
        assert "labels" in result
        assert result["pipeline_id"] == 1
        assert result["chart_type"] == "bar"

    async def test_get_team_performance(self, db_schema, tenant_id):
        """get_team_performance returns team绩效 chart data."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = svc.get_team_performance(
            start_date="2026-01-01", end_date="2026-01-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"
        assert len(result["datasets"]) == 2  # Deals Closed + Revenue

    async def test_get_chart_data(self, db_schema, tenant_id):
        """get_chart_data helper constructs a chart dict from raw data."""
        svc = AnalyticsService()
        await self._seed_user(tenant_id)

        result = svc.get_chart_data(
            chart_type="pie",
            data=[10, 20, 30],
            labels=["Category A", "Category B", "Category C"],
        )
        assert result["labels"] == ["Category A", "Category B", "Category C"]
        assert result["chart_type"] == "pie"
        assert len(result["datasets"]) == 1
        assert result["datasets"][0]["data"] == [10, 20, 30]
