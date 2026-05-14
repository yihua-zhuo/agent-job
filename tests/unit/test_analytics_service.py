"""Unit tests for src/services/analytics_service.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.analytics_service import AnalyticsService
from tests.unit.conftest import (
    MockResult,
    MockRow,
    MockState,
    make_analytics_handlers,
)


class MockDashboardModel:
    """Mock matching DashboardModel interface."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 0)
        self.tenant_id = kwargs.get("tenant_id", 0)
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description")
        self.widgets = kwargs.get("widgets", [])
        self.owner_id = kwargs.get("owner_id", 0)
        self.is_default = kwargs.get("is_default", False)
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "widgets": self.widgets if isinstance(self.widgets, list) else [],
            "owner_id": self.owner_id,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MockReportModel:
    """Mock matching ReportModel interface."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 0)
        self.tenant_id = kwargs.get("tenant_id", 0)
        self.name = kwargs.get("name", "")
        self.type = kwargs.get("type", "sales_revenue")
        self.config = kwargs.get("config", {})
        self.date_range = kwargs.get("date_range", {})
        self.created_by = kwargs.get("created_by", 0)
        self.last_run_at = kwargs.get("last_run_at")
        self.created_at = kwargs.get("created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "type": self.type,
            "config": self.config if isinstance(self.config, dict) else {},
            "date_range": self.date_range if isinstance(self.date_range, dict) else {},
            "created_by": self.created_by,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# mock_db_session fixture
# Builds a standalone mock session (does not wrap make_mock_session handlers
# to avoid the double-wrapping issue where the outer side_effect can't see the
# compiled SQL parameters).
# ---------------------------------------------------------------------------

def _build_analytics_session(state: MockState) -> MagicMock:
    """Build a mock AsyncSession that handles all queries needed by AnalyticsService."""
    session = MagicMock(spec=[
        "execute", "add", "delete", "commit", "rollback",
        "close", "flush", "refresh", "scalars", "scalar_one_or_none",
        "scalar_one", "get", "result", "__aenter__", "__aexit__",
    ])
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.scalars = MagicMock()
    session.scalar_one_or_none = MagicMock()
    session.scalar_one = MagicMock()
    session.result = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    call_count = {}

    def execute_side_effect(sql, params=None, **kwargs):
        call_count["n"] = call_count.get("n", 0) + 1
        sql_text = str(sql).lower().strip()
        # Merge params: explicit positional, SQLAlchemy compiled (via **kwargs),
        # or extracted from compiled statement object when params is None.
        p = dict(params) if params else {}
        p.update(kwargs)
        if not p and hasattr(sql, "compile"):
            try:
                compiled = sql.compile()
                if hasattr(compiled, "params") and isinstance(compiled.params, dict):
                    p = dict(compiled.params)
            except Exception:  # noqa: S110  # best-effort; non-critical SQL param extraction
                pass

        import re

        def _extract_id(sql_t, p, col):
            m = re.search(rf"{re.escape(col)}\s*=\s*:(\w+)", sql_t)
            if m:
                return p.get(m.group(1))
            return None

        # ── Dashboard by id — match only "dashboards.id = :param" ────────────
        # Using "=" guard prevents matching list queries (which have "order by dashboards.id").
        if "from dashboards" in sql_text and "dashboards.id = " in sql_text:
            did = p.get("id") or p.get("id_1") or _extract_id(sql_text, p, "dashboards.id")
            if did == 1:
                return MockResult([MockRow({
                    "id": 1, "tenant_id": 1,
                    "name": "Dashboard 1", "description": "Test dashboard",
                    "widgets": [], "owner_id": 1,
                    "is_default": False,
                    "created_at": None, "updated_at": None,
                })])
            return MockResult([])

        # ── Dashboard list (no equality on dashboards.id) ─────────────────────
        if "from dashboards" in sql_text:
            return MockResult([
                MockRow({
                    "id": 1, "tenant_id": 1,
                    "name": "Dashboard 1", "description": "First",
                    "widgets": [], "owner_id": 1,
                    "is_default": False,
                    "created_at": None, "updated_at": None,
                }),
                MockRow({
                    "id": 2, "tenant_id": 1,
                    "name": "Dashboard 2", "description": "Second",
                    "widgets": [], "owner_id": 1,
                    "is_default": False,
                    "created_at": None, "updated_at": None,
                }),
                MockRow({
                    "id": 3, "tenant_id": 1,
                    "name": "Dashboard 3", "description": "Third",
                    "widgets": [], "owner_id": 1,
                    "is_default": False,
                    "created_at": None, "updated_at": None,
                }),
            ])

        # ── Report by id ──────────────────────────────────────────────────────
        if "from reports" in sql_text and "reports.id = " in sql_text:
            rid = p.get("id") or p.get("id_1") or _extract_id(sql_text, p, "reports.id")
            if rid == 1:
                return MockResult([MockRow({
                    "id": 1, "tenant_id": 1,
                    "name": "Sales Revenue Report",
                    "type": "sales_revenue",
                    "config": {}, "date_range": {},
                    "created_by": 1,
                    "last_run_at": None,
                    "created_at": None,
                })])
            return MockResult([])

        # ── Report list ──────────────────────────────────────────────────────
        if "from reports" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "name": "Sales Revenue Report",
                "type": "sales_revenue",
                "config": {}, "date_range": {},
                "created_by": 1,
                "last_run_at": None,
                "created_at": None,
            })])

        # ── Opportunity queries ───────────────────────────────────────────────
        if "from opportunities" in sql_text:
            if "date_trunc" in sql_text:
                # get_sales_revenue_report
                return MockResult([MockRow({
                    "period": datetime(2024, 1, 15, tzinfo=UTC),
                    "total": 1000.0,
                })])
            # get_team_performance: has owner_id (in SELECT), closed_won in WHERE
            # stage appears as column name in WHERE clause but "closed_won" literal
            # doesn't appear in compiled SQL. Distinguish by presence of "owner_id".
            if "owner_id" in sql_text:
                # Use positional list rows for r[0] (owner_id), r[1] (count), r[2] (sum)
                return MockResult([
                    MockRow([1, 3, 15000.0]),
                    MockRow([2, 2, 8000.0]),
                ])
            if "stage" in sql_text and "count" in sql_text:
                # get_sales_conversion_report — no owner_id
                return MockResult([
                    MockRow({"stage": "lead", "count": 5}),
                    MockRow({"stage": "qualified", "count": 3}),
                    MockRow({"stage": "proposal", "count": 2}),
                    MockRow({"stage": "negotiation", "count": 1}),
                    MockRow({"stage": "closed_won", "count": 1}),
                ])
            # get_pipeline_forecast — has coalesce/sum, no owner_id, no count
            return MockResult([
                MockRow(["lead", 500.0]),
                MockRow(["qualified", 1200.0]),
                MockRow(["proposal", 3000.0]),
                MockRow(["closed_won", 2000.0]),
            ])

        # ── Customer queries ─────────────────────────────────────────────────
        if "from customers" in sql_text:
            if "status" in sql_text and "blocked" in sql_text:
                return MockResult([[2]])
            return MockResult([[10]])

        # ── Fallback to conftest domain handlers ────────────────────────────
        for h in make_analytics_handlers(state):
            result = h(sql_text, p)
            if result is not None:
                return result
        return MockResult([])

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


@pytest.fixture
def mock_db_session():
    """Mock session for AnalyticsService tests."""
    state = MockState()
    session = _build_analytics_session(state)

    async def mock_refresh(obj):
        obj.id = 1

    session.refresh = mock_refresh
    return session


@pytest.fixture
def analytics_service(mock_db_session):
    return AnalyticsService(mock_db_session)


# ---------------------------------------------------------------------------
# TestGetSalesRevenueReport
# ---------------------------------------------------------------------------

class TestGetSalesRevenueReport:
    async def test_get_sales_revenue_report_returns_dict(self, analytics_service):
        result = await analytics_service.get_sales_revenue_report(
            "2024-01-01", "2024-01-31", tenant_id=1,
        )
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "line"


# ---------------------------------------------------------------------------
# TestGetSalesConversionReport
# ---------------------------------------------------------------------------

class TestGetSalesConversionReport:
    async def test_get_sales_conversion_report_returns_dict(self, analytics_service):
        result = await analytics_service.get_sales_conversion_report(
            "2024-01-01", "2024-01-31", tenant_id=1,
        )
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "funnel"


# ---------------------------------------------------------------------------
# TestGetCustomerGrowthReport
# ---------------------------------------------------------------------------

class TestGetCustomerGrowthReport:
    @pytest.fixture
    def session_with_customer(self):
        """Session with customer_handler included for customer growth report."""
        state = MockState()
        session = _build_analytics_session(state)
        return session

    @pytest.fixture
    def svc_with_customer(self, session_with_customer):
        return AnalyticsService(session_with_customer)

    async def test_get_customer_growth_report_returns_dict(self, svc_with_customer):
        result = await svc_with_customer.get_customer_growth_report(
            "2024-01-01", "2024-01-31", tenant_id=1,
        )
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"


# ---------------------------------------------------------------------------
# TestGetPipelineForecast
# ---------------------------------------------------------------------------

class TestGetPipelineForecast:
    async def test_get_pipeline_forecast_returns_dict(self, analytics_service):
        result = await analytics_service.get_pipeline_forecast(
            pipeline_id=1, tenant_id=1,
        )
        assert isinstance(result, dict)
        assert "pipeline_id" in result
        assert result["pipeline_id"] == 1
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"


# ---------------------------------------------------------------------------
# TestGetTeamPerformance
# ---------------------------------------------------------------------------

class TestGetTeamPerformance:
    async def test_get_team_performance_returns_dict(self, analytics_service):
        result = await analytics_service.get_team_performance(
            "2024-01-01", "2024-01-31", tenant_id=1,
        )
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "bar"
        # Verify owner data was returned
        assert len(result["labels"]) == 2
        assert result["labels"][0] == "Owner 1"


# ---------------------------------------------------------------------------
# TestDashboardCrud
# ---------------------------------------------------------------------------

class TestDashboardCrud:
    async def test_create_dashboard_success(self, mock_db_session):
        svc = AnalyticsService(mock_db_session)
        result = await svc.create_dashboard(
            name="Sales", owner_id=1, tenant_id=1,
        )
        assert result.name == "Sales"
        assert result.widgets == []

    async def test_get_dashboard_found(self, analytics_service):
        result = await analytics_service.get_dashboard(1, tenant_id=1)
        assert result.name == "Dashboard 1"

    async def test_get_dashboard_not_found(self, mock_db_session):
        svc = AnalyticsService(mock_db_session)
        with pytest.raises(NotFoundException):
            await svc.get_dashboard(9999, tenant_id=1)

    async def test_list_dashboards_pagination(self, analytics_service):
        items = await analytics_service.list_dashboards(tenant_id=1)
        assert len(items) == 3


# ---------------------------------------------------------------------------
# TestReportDispatch
# ---------------------------------------------------------------------------

class TestReportDispatch:
    async def test_run_report_dispatches_to_sales_revenue(self, mock_db_session):
        svc = AnalyticsService(mock_db_session)

        result = await svc.run_report(
            report_id=1,
            date_range={"start": "2024-01-01", "end": "2024-01-31"},
            tenant_id=1,
        )

        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert result["chart_type"] == "line"
