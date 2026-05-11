"""
Integration tests for Analytics and Report services.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_analytics_integration.py -v
"""
from __future__ import annotations

import uuid

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.analytics_service import AnalyticsService
from services.report_service import ReportService
from services.user_service import UserService


async def _seed_user(tenant_id: int, async_session, prefix: str = "user") -> int:
    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=f"{prefix}_{suffix}",
        email=f"{prefix}_{suffix}@example.com",
        password="Test@Pass1234",
        tenant_id=tenant_id,
    )
    return reg.id


# ──────────────────────────────────────────────────────────────────────────────────────
#  Dashboard integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestDashboardIntegration:
    """Full dashboard lifecycle via the real DB."""

    async def test_create_and_get_dashboard(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")

        result = await svc.create_dashboard(
            name="Sales Overview",
            owner_id=uid,
            tenant_id=tenant_id,
            description="Main sales metrics dashboard",
        )
        assert result.name == "Sales Overview"
        assert result.owner_id == uid
        assert result.description == "Main sales metrics dashboard"
        assert result.widgets == []

        fetched = await svc.get_dashboard(result.id, tenant_id=tenant_id)
        assert fetched.name == "Sales Overview"

    async def test_update_dashboard(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")

        created = await svc.create_dashboard(
            name="Original Name", owner_id=uid, tenant_id=tenant_id,
        )

        updated = await svc.update_dashboard(
            dashboard_id=created.id,
            tenant_id=tenant_id,
            name="Updated Name",
            description="New description",
            widgets=[{"type": "chart", "config": {"chartType": "bar"}}],
        )
        assert updated.name == "Updated Name"
        assert updated.description == "New description"
        assert len(updated.widgets) == 1

    async def test_get_dashboard_not_found(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_dashboard(dashboard_id=999_999_999, tenant_id=tenant_id)

    async def test_list_dashboards(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")
        suffix = uuid.uuid4().hex[:8]

        await svc.create_dashboard(name=f"Dash A {suffix}", owner_id=uid, tenant_id=tenant_id)
        await svc.create_dashboard(name=f"Dash B {suffix}", owner_id=uid, tenant_id=tenant_id)

        items = await svc.list_dashboards(tenant_id=tenant_id)
        names = [d.name for d in items]
        assert any(f"Dash A {suffix}" in n for n in names)
        assert any(f"Dash B {suffix}" in n for n in names)

    async def test_list_dashboards_by_owner(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid1 = await _seed_user(tenant_id, async_session, "dash1")
        uid2 = await _seed_user(tenant_id, async_session, "dash2")
        suffix = uuid.uuid4().hex[:8]

        await svc.create_dashboard(name=f"Owner1 Dash {suffix}", owner_id=uid1, tenant_id=tenant_id)
        await svc.create_dashboard(name=f"Owner2 Dash {suffix}", owner_id=uid2, tenant_id=tenant_id)

        items = await svc.list_dashboards(tenant_id=tenant_id, owner_id=uid1)
        assert all(d.owner_id == uid1 for d in items)

    async def test_dashboard_cross_tenant_isolation(
        self, db_schema, tenant_id, tenant_id_2, async_session
    ):
        svc = AnalyticsService(async_session)
        uid1 = await _seed_user(tenant_id, async_session, "dashT1")
        uid2 = await _seed_user(tenant_id_2, async_session, "dashT2")

        d1 = await svc.create_dashboard(name="Tenant 1 Dash", owner_id=uid1, tenant_id=tenant_id)
        d2 = await svc.create_dashboard(name="Tenant 2 Dash", owner_id=uid2, tenant_id=tenant_id_2)

        items_t1 = await svc.list_dashboards(tenant_id=tenant_id)
        ids_t1 = [d.id for d in items_t1]
        assert d1.id in ids_t1
        assert d2.id not in ids_t1

        items_t2 = await svc.list_dashboards(tenant_id=tenant_id_2)
        ids_t2 = [d.id for d in items_t2]
        assert d2.id in ids_t2
        assert d1.id not in ids_t2

    async def test_add_widget_to_dashboard(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")

        created = await svc.create_dashboard(name="Widget Test", owner_id=uid, tenant_id=tenant_id)

        widget = await svc.add_widget(
            dashboard_id=created.id, tenant_id=tenant_id,
            widget_config={"type": "kpi", "config": {"metric": "revenue"}},
        )
        assert widget is not None

        fetched = await svc.get_dashboard(created.id, tenant_id=tenant_id)
        assert len(fetched.widgets) >= 1

    async def test_remove_widget_from_dashboard(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")

        created = await svc.create_dashboard(
            name="Remove Widget Test", owner_id=uid, tenant_id=tenant_id,
        )

        await svc.add_widget(
            dashboard_id=created.id, tenant_id=tenant_id,
            widget_config={"type": "chart", "config": {"chartType": "line"}},
        )
        add_result = await svc.add_widget(
            dashboard_id=created.id, tenant_id=tenant_id,
            widget_config={"type": "kpi", "config": {"metric": "count"}},
        )
        widget_id = add_result["id"]

        removed = await svc.remove_widget(
            dashboard_id=created.id, widget_id=widget_id, tenant_id=tenant_id,
        )
        assert removed is True

    async def test_dashboard_is_default_flag(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "dash")

        created = await svc.create_dashboard(name="Default Dash", owner_id=uid, tenant_id=tenant_id)
        assert created.is_default is False

        updated = await svc.update_dashboard(
            dashboard_id=created.id, tenant_id=tenant_id, is_default=True,
        )
        assert updated.is_default is True


# ──────────────────────────────────────────────────────────────────────────────────────
#  Report integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestReportIntegration:
    """Report generation and export via the real DB."""

    async def test_create_and_get_report(self, db_schema, tenant_id, async_session):
        analytics_svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "rep")

        result = await analytics_svc.create_report(
            name="Monthly Sales Report",
            report_type="sales_revenue",
            config={"orientation": "portrait"},
            created_by=uid,
            tenant_id=tenant_id,
        )
        assert result.name == "Monthly Sales Report"
        assert result.type == "sales_revenue"
        assert result.created_by == uid

    async def test_create_report_different_types(self, db_schema, tenant_id, async_session):
        analytics_svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "rep")

        for rtype in ["sales_revenue", "sales_conversion", "customer_growth", "pipeline_forecast"]:
            result = await analytics_svc.create_report(
                name=f"Report {rtype}",
                report_type=rtype,
                config={},
                created_by=uid,
                tenant_id=tenant_id,
            )
            assert result.type == rtype

    async def test_generate_pdf_report(self, db_schema, tenant_id, async_session):
        svc = ReportService(async_session)
        await _seed_user(tenant_id, async_session, "rep")

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

    async def test_generate_excel_report(self, db_schema, tenant_id, async_session):
        svc = ReportService(async_session)
        await _seed_user(tenant_id, async_session, "rep")

        generated = svc.generate_excel_report(
            report_data={
                "labels": ["Product A", "Product B"],
                "datasets": [{"data": [500, 750]}],
            },
            title="Monthly Sales Excel",
        )
        assert generated["status"] == "generated"
        assert generated["format"] == "excel"

    async def test_export_to_csv(self, db_schema, tenant_id, async_session):
        svc = ReportService(async_session)
        await _seed_user(tenant_id, async_session, "rep")

        data = [
            {"name": "Alice", "email": "alice@example.com", "amount": 1000},
            {"name": "Bob", "email": "bob@example.com", "amount": 2000},
        ]
        filename = f"test_export_{uuid.uuid4().hex[:8]}.csv"

        result = svc.export_to_csv(data=data, filename=filename)
        assert result["status"] == "success"
        assert result["rows_exported"] == 2
        assert filename in result["filename"]

    async def test_export_to_csv_empty_data(self, db_schema, tenant_id, async_session):
        svc = ReportService(async_session)
        with pytest.raises(ValidationException):
            svc.export_to_csv(data=[], filename="empty.csv")

    async def test_schedule_report(self, db_schema, tenant_id, async_session):
        analytics_svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "rep")

        created = await analytics_svc.create_report(
            name="Scheduled Report",
            report_type="sales_revenue",
            config={},
            created_by=uid,
            tenant_id=tenant_id,
        )

        report_svc = ReportService(async_session)
        schedule = {
            "frequency": "daily",
            "time": "09:00",
            "timezone": "UTC",
            "recipients": ["team@example.com"],
        }
        result = await report_svc.schedule_report(
            report_id=created.id, schedule=schedule, tenant_id=tenant_id,
        )
        assert result.report_id == created.id
        assert result.schedule["frequency"] == "daily"
        assert result.active is True

    async def test_schedule_report_multiple(self, db_schema, tenant_id, async_session):
        analytics_svc = AnalyticsService(async_session)
        uid = await _seed_user(tenant_id, async_session, "rep")

        created = await analytics_svc.create_report(
            name="Re-scheduled Report",
            report_type="sales_conversion",
            config={},
            created_by=uid,
            tenant_id=tenant_id,
        )

        report_svc = ReportService(async_session)
        await report_svc.schedule_report(
            report_id=created.id,
            schedule={"frequency": "daily", "time": "09:00", "timezone": "UTC", "recipients": []},
            tenant_id=tenant_id,
        )
        updated = await report_svc.schedule_report(
            report_id=created.id,
            schedule={"frequency": "weekly", "time": "10:00", "timezone": "UTC", "recipients": []},
            tenant_id=tenant_id,
        )
        assert updated.schedule["frequency"] == "weekly"


# ──────────────────────────────────────────────────────────────────────────────────────
#  Aggregated report queries — query real DB
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestChartHelpersIntegration:
    """Aggregated reports that query customers/opportunities."""

    async def test_get_sales_revenue_report(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        result = await svc.get_sales_revenue_report(
            start_date="2026-01-01", end_date="2026-01-31",
            group_by="day", tenant_id=tenant_id,
        )
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "line"

    async def test_get_sales_conversion_report(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        result = await svc.get_sales_conversion_report(
            start_date="2026-01-01", end_date="2026-01-31", tenant_id=tenant_id,
        )
        assert "labels" in result
        assert result["chart_type"] == "funnel"

    async def test_get_customer_growth_report(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        result = await svc.get_customer_growth_report(
            start_date="2026-01-01", end_date="2026-03-31", tenant_id=tenant_id,
        )
        assert "labels" in result
        assert result["chart_type"] == "bar"

    async def test_get_pipeline_forecast(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        result = await svc.get_pipeline_forecast(pipeline_id=1, tenant_id=tenant_id)
        assert "labels" in result
        assert result["pipeline_id"] == 1
        assert result["chart_type"] == "bar"

    async def test_get_team_performance(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        result = await svc.get_team_performance(
            start_date="2026-01-01", end_date="2026-01-31", tenant_id=tenant_id,
        )
        assert "labels" in result
        assert result["chart_type"] == "bar"
        assert len(result["datasets"]) == 2

    def test_get_chart_data(self):
        """Sync utility — no DB needed."""
        from unittest.mock import MagicMock
        svc = AnalyticsService(MagicMock())
        result = svc.get_chart_data(
            chart_type="pie", data=[10, 20, 30],
            labels=["A", "B", "C"],
        )
        assert result["labels"] == ["A", "B", "C"]
        assert result["chart_type"] == "pie"
