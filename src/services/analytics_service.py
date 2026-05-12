"""Analytics service — DB-backed dashboards & reports + aggregated query reports."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.analytics import DashboardModel, ReportModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException


class AnalyticsService:
    """Backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Dashboard CRUD
    # -------------------------------------------------------------------------

    async def create_dashboard(
        self,
        name: str,
        owner_id: int,
        tenant_id: int = 0,
        description: str | None = None,
    ) -> DashboardModel:
        now = datetime.now(UTC)
        dashboard = DashboardModel(
            tenant_id=tenant_id,
            name=name,
            description=description,
            widgets=[],
            owner_id=owner_id,
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(dashboard)
        await self.session.flush()
        await self.session.refresh(dashboard)
        return dashboard

    async def get_dashboard(self, dashboard_id: int, tenant_id: int = 0) -> DashboardModel:
        result = await self.session.execute(
            select(DashboardModel).where(and_(DashboardModel.id == dashboard_id, DashboardModel.tenant_id == tenant_id))
        )
        dashboard = result.scalar_one_or_none()
        if dashboard is None:
            raise NotFoundException("Dashboard")
        return dashboard

    async def update_dashboard(self, dashboard_id: int, tenant_id: int = 0, **kwargs) -> DashboardModel:
        dashboard = await self.get_dashboard(dashboard_id, tenant_id)
        allowed = {"name", "description", "widgets", "is_default"}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(dashboard, key, value)
        dashboard.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(dashboard)
        return dashboard

    async def list_dashboards(
        self,
        tenant_id: int = 0,
        owner_id: int | None = None,
    ) -> list[DashboardModel]:
        conditions = [DashboardModel.tenant_id == tenant_id]
        if owner_id is not None:
            conditions.append(DashboardModel.owner_id == owner_id)
        result = await self.session.execute(select(DashboardModel).where(and_(*conditions)).order_by(DashboardModel.id))
        return result.scalars().all()

    async def add_widget(self, dashboard_id: int, widget_config: dict, tenant_id: int = 0) -> dict:
        dashboard = await self.get_dashboard(dashboard_id, tenant_id)
        widgets = list(dashboard.widgets or [])
        widget = {"id": len(widgets) + 1, **widget_config}
        widgets.append(widget)
        dashboard.widgets = widgets
        dashboard.updated_at = datetime.now(UTC)
        await self.session.flush()
        return widget

    async def remove_widget(self, dashboard_id: int, widget_id: int, tenant_id: int = 0) -> bool:
        dashboard = await self.get_dashboard(dashboard_id, tenant_id)
        widgets = [w for w in (dashboard.widgets or []) if w.get("id") != widget_id]
        dashboard.widgets = widgets
        dashboard.updated_at = datetime.now(UTC)
        await self.session.flush()
        return True

    # -------------------------------------------------------------------------
    # Report CRUD
    # -------------------------------------------------------------------------

    async def create_report(
        self,
        name: str,
        report_type: str,
        config: dict,
        created_by: int,
        tenant_id: int = 0,
    ) -> ReportModel:
        report = ReportModel(
            tenant_id=tenant_id,
            name=name,
            type=report_type,
            config=config,
            date_range={},
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def get_report(self, report_id: int, tenant_id: int = 0) -> ReportModel:
        result = await self.session.execute(
            select(ReportModel).where(and_(ReportModel.id == report_id, ReportModel.tenant_id == tenant_id))
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise NotFoundException("Report")
        return report

    async def run_report(self, report_id: int, date_range: dict, tenant_id: int = 0) -> dict:
        report = await self.get_report(report_id, tenant_id)
        report.date_range = date_range
        report.last_run_at = datetime.now(UTC)
        await self.session.flush()

        start = date_range.get("start")
        end = date_range.get("end")

        if report.type == "sales_revenue":
            return await self.get_sales_revenue_report(start, end, tenant_id=tenant_id)
        if report.type == "sales_conversion":
            return await self.get_sales_conversion_report(start, end, tenant_id=tenant_id)
        if report.type == "customer_growth":
            return await self.get_customer_growth_report(start, end, tenant_id=tenant_id)
        if report.type == "pipeline_forecast":
            return await self.get_pipeline_forecast(date_range.get("pipeline_id"), tenant_id=tenant_id)
        if report.type == "team_performance":
            return await self.get_team_performance(start, end, tenant_id=tenant_id)
        return {"error": "Unknown report type"}

    # -------------------------------------------------------------------------
    # Aggregated reports — query real DB
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_date(d):
        if d is None:
            return None
        if isinstance(d, str):
            return datetime.fromisoformat(d)
        return d

    async def get_sales_revenue_report(
        self,
        start_date,
        end_date,
        group_by: str = "day",
        tenant_id: int = 0,
    ) -> dict:
        """Sum opportunity amount per period within [start, end]."""
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)

        labels: list[str] = []
        data: list[float] = []

        if start and end:
            # Build label periods
            periods: list[datetime] = []
            current = start
            while current <= end:
                periods.append(current)
                if group_by == "week":
                    current += timedelta(weeks=1)
                elif group_by == "month":
                    month = current.month + 1
                    year = current.year + (month // 13)
                    month = month % 13 or 12
                    current = current.replace(year=year, month=month)
                else:
                    current += timedelta(days=1)

            labels = [p.strftime("%Y-%m-%d") for p in periods]

            # Sum revenue per period from opportunities
            result = await self.session.execute(
                select(
                    func.date_trunc(group_by, OpportunityModel.created_at).label("period"),
                    func.coalesce(func.sum(OpportunityModel.amount), 0).label("total"),
                )
                .where(
                    and_(
                        OpportunityModel.tenant_id == tenant_id,
                        OpportunityModel.created_at >= start,
                        OpportunityModel.created_at <= end,
                    )
                )
                .group_by("period")
            )
            rows = {r._mapping["period"].strftime("%Y-%m-%d"): float(r._mapping["total"]) for r in result.fetchall()}
            data = [rows.get(lbl, 0.0) for lbl in labels]

        return {
            "labels": labels,
            "datasets": [{"label": "Sales Revenue", "data": data, "color": "#4F46E5"}],
            "chart_type": "line",
        }

    async def get_sales_conversion_report(self, start_date, end_date, tenant_id: int = 0) -> dict:
        """Count opportunities by stage."""
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)

        conditions = [OpportunityModel.tenant_id == tenant_id]
        if start:
            conditions.append(OpportunityModel.created_at >= start)
        if end:
            conditions.append(OpportunityModel.created_at <= end)

        result = await self.session.execute(
            select(OpportunityModel.stage, func.count(OpportunityModel.id))
            .where(and_(*conditions))
            .group_by(OpportunityModel.stage)
        )
        counts = {row[0]: row[1] for row in result.fetchall()}

        stages = ["lead", "qualified", "proposal", "negotiation", "closed_won"]
        labels = ["Leads", "Qualified", "Proposal", "Negotiation", "Closed Won"]
        data = [counts.get(s, 0) for s in stages]
        return {
            "labels": labels,
            "datasets": [{"label": "Conversion", "data": data, "color": "#10B981"}],
            "chart_type": "funnel",
        }

    async def get_customer_growth_report(self, start_date, end_date, tenant_id: int = 0) -> dict:
        """Count new and churned customers in the period."""
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)

        conditions = [CustomerModel.tenant_id == tenant_id]
        if start:
            conditions.append(CustomerModel.created_at >= start)
        if end:
            conditions.append(CustomerModel.created_at <= end)

        new_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
        new_count = new_result.scalar() or 0

        churned_result = await self.session.execute(
            select(func.count(CustomerModel.id)).where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    CustomerModel.status == "blocked",
                )
            )
        )
        churned = churned_result.scalar() or 0

        return {
            "labels": ["New Customers", "Churned", "Net Growth"],
            "datasets": [
                {
                    "label": "Customer Growth",
                    "data": [new_count, churned, new_count - churned],
                    "color": "#F59E0B",
                }
            ],
            "chart_type": "bar",
        }

    async def get_pipeline_forecast(self, pipeline_id, tenant_id: int = 0) -> dict:
        """Expected revenue by stage = sum(amount * probability/100)."""
        conditions = [OpportunityModel.tenant_id == tenant_id]
        if pipeline_id is not None and pipeline_id != "default":
            conditions.append(OpportunityModel.pipeline_id == pipeline_id)

        result = await self.session.execute(
            select(
                OpportunityModel.stage,
                func.coalesce(
                    func.sum(OpportunityModel.amount * OpportunityModel.probability / 100),
                    0,
                ),
            )
            .where(and_(*conditions))
            .group_by(OpportunityModel.stage)
        )
        rows = {r[0]: float(r[1]) for r in result.fetchall()}

        stages = ["lead", "qualified", "proposal", "closed_won"]
        labels = ["Stage 1", "Stage 2", "Stage 3", "Closed"]
        data = [rows.get(s, 0.0) for s in stages]
        return {
            "pipeline_id": pipeline_id or "default",
            "labels": labels,
            "datasets": [{"label": "Expected Revenue", "data": data, "color": "#8B5CF6"}],
            "chart_type": "bar",
        }

    async def get_team_performance(self, start_date, end_date, tenant_id: int = 0) -> dict:
        """Aggregate closed-won deals per owner."""
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)

        conditions = [
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.stage == "closed_won",
        ]
        if start:
            conditions.append(OpportunityModel.created_at >= start)
        if end:
            conditions.append(OpportunityModel.created_at <= end)

        result = await self.session.execute(
            select(
                OpportunityModel.owner_id,
                func.count(OpportunityModel.id),
                func.coalesce(func.sum(OpportunityModel.amount), 0),
            )
            .where(and_(*conditions))
            .group_by(OpportunityModel.owner_id)
            .order_by(OpportunityModel.owner_id)
        )
        rows = result.fetchall()

        labels = [f"Owner {r[0]}" for r in rows]
        deals = [int(r[1]) for r in rows]
        revenue = [float(r[2]) for r in rows]
        return {
            "labels": labels,
            "datasets": [
                {"label": "Deals Closed", "data": deals, "color": "#EC4899"},
                {"label": "Revenue", "data": revenue, "color": "#3B82F6"},
            ],
            "chart_type": "bar",
        }

    def get_chart_data(self, chart_type: str, data: list, labels: list[str]) -> dict:
        """Format raw data into a chart structure (sync utility, no DB)."""
        return {
            "labels": labels,
            "datasets": [{"label": "Data", "data": data, "color": "#6366F1"}],
            "chart_type": chart_type,
        }
