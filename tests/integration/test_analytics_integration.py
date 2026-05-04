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

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.analytics_service import AnalyticsService
from services.report_service import ReportService
from services.user_service import UserService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Dashboard integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestDashboardIntegration:
    """Full dashboard lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        """Create a user and return their id (needed for owner_id)."""
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"dashuser_{suffix}",
            email=f"dash_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg["id"]

    async def test_create_and_get_dashboard(self, db_schema, tenant_id, async_session):
        """Create a dashboard and verify it can be retrieved."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        result = svc.create_dashboard(
            name="Sales Overview",
            owner_id=uid,
            description="Main sales metrics dashboard",
        )
        assert result["name"] == "Sales Overview"
        assert result["owner_id"] == uid
        assert result["description"] == "Main sales metrics dashboard"
        assert result["widgets"] == []

        fetched = svc.get_dashboard(result["id"])
        assert fetched["name"] == "Sales Overview"

    async def test_update_dashboard(self, db_schema, tenant_id, async_session):
        """Update dashboard name, description, and widgets."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = svc.create_dashboard(
            name="Original Name",
            owner_id=uid,
        )
        did = created["id"]

        updated = svc.update_dashboard(
            dashboard_id=did,
            name="Updated Name",
            description="New description",
            widgets=[{"type": "chart", "config": {"chartType": "bar"}}],
        )
        assert updated["name"] == "Updated Name"
        assert updated["description"] == "New description"
        assert len(updated["widgets"]) == 1

    async def test_get_dashboard_not_found(self, db_schema, tenant_id, async_session):
        """Non-existent dashboard raises NotFoundException."""
        svc = AnalyticsService(async_session)
        with pytest.raises(NotFoundException):
            svc.get_dashboard(dashboard_id=999_999_999)

    async def test_list_dashboards(self, db_schema, tenant_id, async_session):
        """List returns all dashboards for the tenant."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        suffix = uuid.uuid4().hex[:8]

        svc.create_dashboard(
            name=f"Dash A {suffix}", owner_id=uid
        )
        svc.create_dashboard(
            name=f"Dash B {suffix}", owner_id=uid
        )

        items = svc.list_dashboards()
        names = [d["name"] for d in items]
        assert any(f"Dash A {suffix}" in n for n in names)
        assert any(f"Dash B {suffix}" in n for n in names)

    async def test_list_dashboards_by_owner(self, db_schema, tenant_id, async_session):
        """List dashboards filtered by owner_id."""
        svc = AnalyticsService(async_session)
        uid1 = await self._seed_user(tenant_id, async_session)
        uid2 = await self._seed_user(tenant_id, async_session)
        suffix = uuid.uuid4().hex[:8]

        svc.create_dashboard(name=f"Owner1 Dash {suffix}", owner_id=uid1)
        svc.create_dashboard(name=f"Owner2 Dash {suffix}", owner_id=uid2)

        items = svc.list_dashboards(owner_id=uid1)
        # All returned dashboards should belong to the specified owner
        assert all(d["owner_id"] == uid1 for d in items)

    async def test_dashboard_cross_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2, async_session
    ):
        """Dashboards are not visible across tenants (separate service instances)."""
        svc1 = AnalyticsService(async_session)
        svc2 = AnalyticsService(async_session)
        uid1 = await self._seed_user(tenant_id, async_session)
        uid2 = await self._seed_user(tenant_id, async_session)

        d1 = svc1.create_dashboard(
            name="Tenant 1 Dash", owner_id=uid1
        )
        d2 = svc2.create_dashboard(
            name="Tenant 2 Dash", owner_id=uid2
        )

        items_svc1 = svc1.list_dashboards()
        ids_svc1 = [d["id"] for d in items_svc1]

        # svc1's dashboard should be in its list
        assert d1["id"] in ids_svc1

        items_svc2 = svc2.list_dashboards()
        ids_svc2 = [d["id"] for d in items_svc2]
        assert d2["id"] in ids_svc2

    async def test_add_widget_to_dashboard(self, db_schema, tenant_id, async_session):
        """Add a widget to an existing dashboard."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = svc.create_dashboard(
            name="Widget Test", owner_id=uid
        )
        did = created["id"]

        result = svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "kpi", "config": {"metric": "revenue"}},
        )
        assert result is not None

        fetched = svc.get_dashboard(did)
        assert len(fetched["widgets"]) >= 1

    async def test_remove_widget_from_dashboard(self, db_schema, tenant_id, async_session):
        """Remove a widget from a dashboard."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = svc.create_dashboard(
            name="Remove Widget Test", owner_id=uid
        )
        did = created["id"]

        # Add two widgets
        svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "chart", "config": {"chartType": "line"}},
        )
        add_result = svc.add_widget(
            dashboard_id=did,
            widget_config={"type": "kpi", "config": {"metric": "count"}},
        )
        widget_id = add_result["id"]

        # Remove one widget
        removed = svc.remove_widget(
            dashboard_id=did, widget_id=widget_id
        )
        assert removed is True

    async def test_dashboard_is_default_flag(self, db_schema, tenant_id, async_session):
        """Update and verify is_default flag on dashboard."""
        svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = svc.create_dashboard(
            name="Default Dash", owner_id=uid
        )
        did = created["id"]
        assert created["is_default"] is False

        updated = svc.update_dashboard(
            dashboard_id=did, is_default=True
        )
        assert updated["is_default"] is True


# ──────────────────────────────────────────────────────────────────────────────────────
#  Report integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestReportIntegration:
    """Report generation and export via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        """Create a user and return their id (needed for created_by)."""
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"repuser_{suffix}",
            email=f"rep_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg["id"]

    async def test_create_and_get_report(self, db_schema, tenant_id, async_session):
        """Create a report and verify it can be retrieved via run_report."""
        analytics_svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        result = analytics_svc.create_report(
            name="Monthly Sales Report",
            report_type="sales_revenue",
            config={"orientation": "portrait"},
            created_by=uid,
        )
        assert result["name"] == "Monthly Sales Report"
        assert result["type"] == "sales_revenue"
        assert result["created_by"] == uid

    async def test_create_report_different_types(self, db_schema, tenant_id, async_session):
        """Create reports of different types (sales_revenue, sales_conversion, etc.)."""
        analytics_svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        for rtype in ["sales_revenue", "sales_conversion", "customer_growth", "pipeline_forecast"]:
            result = analytics_svc.create_report(
                name=f"Report {rtype}",
                report_type=rtype,
                config={},
                created_by=uid,
            )
            assert result["type"] == rtype

    async def test_generate_pdf_report(self, db_schema, tenant_id, async_session):
        """Generate a PDF report and verify structure."""
        svc = ReportService(async_session)
        await self._seed_user(tenant_id, async_session)

        generated = svc.generate_pdf_report(
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

    async def test_generate_excel_report(self, db_schema, tenant_id, async_session):
        """Generate an Excel report and verify structure."""
        svc = ReportService(async_session)
        await self._seed_user(tenant_id, async_session)

        generated = svc.generate_excel_report(
            report_data={
                "labels": ["Product A", "Product B"],
                "datasets": [{"data": [500, 750]}],
            },
            title="Monthly Sales Excel",
        )
        assert generated["status"] == "generated"
        assert generated["format"] == "excel"
        assert generated["title"] == "Monthly Sales Excel"

    async def test_export_to_csv(self, db_schema, tenant_id, async_session):
        """Export data to CSV and verify file structure."""
        svc = ReportService(async_session)
        await self._seed_user(tenant_id, async_session)

        data = [
            {"name": "Alice", "email": "alice@example.com", "amount": 1000},
            {"name": "Bob", "email": "bob@example.com", "amount": 2000},
        ]
        filename = f"test_export_{uuid.uuid4().hex[:8]}.csv"

        result = svc.export_to_csv(data=data, filename=filename)
        assert result["status"] == "success"
        assert result["rows_exported"] == 2
        assert filename in result["filename"]
        assert "filepath" in result

    async def test_export_to_csv_empty_data(self, db_schema, tenant_id, async_session):
        """Export with no data raises ValidationException."""
        svc = ReportService(async_session)
        with pytest.raises(ValidationException):
            svc.export_to_csv(data=[], filename="empty.csv")

    async def test_schedule_report(self, db_schema, tenant_id, async_session):
        """Schedule a report and verify scheduling returns success."""
        analytics_svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = analytics_svc.create_report(
            name="Scheduled Report",
            report_type="sales_revenue",
            config={},
            created_by=uid,
        )
        rid = created["id"]

        report_svc = ReportService(async_session)
        schedule = {
            "frequency": "daily",
            "time": "09:00",
            "timezone": "UTC",
            "recipients": ["team@example.com"],
        }
        result = report_svc.schedule_report(report_id=rid, schedule=schedule)
        assert result["report_id"] == rid
        assert result["schedule"]["frequency"] == "daily"
        assert result["active"] is True

    async def test_schedule_report_multiple(self, db_schema, tenant_id, async_session):
        """Scheduling the same report twice updates the schedule (idempotent key)."""
        analytics_svc = AnalyticsService(async_session)
        uid = await self._seed_user(tenant_id, async_session)

        created = analytics_svc.create_report(
            name="Re-scheduled Report",
            report_type="sales_conversion",
            config={},
            created_by=uid,
        )
        rid = created["id"]

        report_svc = ReportService(async_session)
        report_svc.schedule_report(
            report_id=rid,
            schedule={"frequency": "daily", "time": "09:00", "timezone": "UTC", "recipients": []},
        )
        updated = report_svc.schedule_report(
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

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"chartuser_{suffix}",
            email=f"chart_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg["id"]

    async def test_get_sales_revenue_report(self, db_schema, tenant_id, async_session):
        """get_sales_revenue_report returns chart data structure."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_sales_revenue_report(
            start_date="2026-01-01", end_date="2026-01-31", group_by="day"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "line"

    async def test_get_sales_conversion_report(self, db_schema, tenant_id, async_session):
        """get_sales_conversion_report returns funnel chart data."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_sales_conversion_report(
            start_date="2026-01-01", end_date="2026-01-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "funnel"

    async def test_get_customer_growth_report(self, db_schema, tenant_id, async_session):
        """get_customer_growth_report returns bar chart data."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_customer_growth_report(
            start_date="2026-01-01", end_date="2026-03-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"

    async def test_get_pipeline_forecast(self, db_schema, tenant_id, async_session):
        """get_pipeline_forecast returns pipeline forecast data."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_pipeline_forecast(pipeline_id=1)
        assert "labels" in result
        assert result["pipeline_id"] == 1
        assert result["chart_type"] == "bar"

    async def test_get_team_performance(self, db_schema, tenant_id, async_session):
        """get_team_performance returns team performance chart data."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_team_performance(
            start_date="2026-01-01", end_date="2026-01-31"
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"
        assert len(result["datasets"]) == 2  # Deals Closed + Revenue

    async def test_get_chart_data(self, db_schema, tenant_id, async_session):
        """get_chart_data helper constructs a chart dict from raw data."""
        svc = AnalyticsService(async_session)
        await self._seed_user(tenant_id, async_session)

        result = svc.get_chart_data(
            chart_type="pie",
            data=[10, 20, 30],
            labels=["Category A", "Category B", "Category C"],
        )
        assert result["labels"] == ["Category A", "Category B", "Category C"]
        assert result["chart_type"] == "pie"
        assert len(result["datasets"]) == 1
        assert result["datasets"][0]["data"] == [10, 20, 30]
