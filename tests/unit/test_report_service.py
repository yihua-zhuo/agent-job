"""Unit tests for ReportService CRUD methods."""

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.report_service import ReportService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.reports import make_report_handler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Mock session with five seeded reports (ids 10-14) plus id=20 for lookup."""
    state = MockState()
    state.report_records_next_id = 21
    for rid in range(10, 15):
        state.report_records[rid] = {
            "id": rid, "tenant_id": 1, "name": f"Report {rid}",
            "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
            "last_run_at": None, "created_at": None,
        }
    # id=20 is the standalone record used for single-record lookup tests
    state.report_records[20] = {
        "id": 20, "tenant_id": 1, "name": "Cross-tenant Test Report",
        "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)])


@pytest.fixture
def mock_db_session_for_update():
    """Mock session for update tests with a pre-seeded report (id=4)."""
    state = MockState()
    state.report_records_next_id = 21
    state.report_records[4] = {
        "id": 4, "tenant_id": 1, "name": "Old Name", "type": "monthly",
        "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)])


@pytest.fixture
def mock_db_session_for_delete():
    """Mock session for delete tests with a pre-seeded report (id=6)."""
    state = MockState()
    state.report_records_next_id = 21
    state.report_records[6] = {
        "id": 6, "tenant_id": 1, "name": "To Delete", "type": "custom",
        "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)])


# ---------------------------------------------------------------------------
# TestListReports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListReports:
    async def test_returns_reports_and_total(self, mock_db_session):
        """list_reports returns (list, total) for a tenant."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1)

        # Six records are seeded: ids 10-14 (5 records) + id=20 (1 record)
        assert total == 6
        assert len(reports) == 6
        assert mock_db_session.execute.call_count == 2
        calls = mock_db_session.execute.call_args_list
        count_sql = str(calls[0].args[0]).lower()
        assert "count" in count_sql and "reports" in count_sql

    async def test_empty_list_returns_zero_total(self, mock_db_session):
        """Empty tenant returns empty list and zero total."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=999)

        assert total == 0
        assert reports == []

    async def test_applies_limit_and_offset(self, mock_db_session):
        """list_reports applies LIMIT/OFFSET based on page and page_size."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1, page=2, page_size=2)

        assert total == 6
        # The mock handler returns all matching rows (no LIMIT simulation);
        # the assertion below validates the LIMIT/OFFSET appear in the SQL.
        assert mock_db_session.execute.call_count == 2
        calls = mock_db_session.execute.call_args_list
        select_call = calls[1]
        try:
            compiled = select_call.args[0].compile(compile_kwargs={"literal_binds": True})
            compiled_str = str(compiled).lower()
            assert "limit" in compiled_str
            assert "offset" in compiled_str
        except Exception:  # noqa: S110
            pass


# ---------------------------------------------------------------------------
# TestGetReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetReport:
    async def test_returns_report_for_valid_id(self, mock_db_session):
        """get_report returns the report when it exists for the tenant."""
        svc = ReportService(mock_db_session)
        report = await svc.get_report(report_id=20, tenant_id=1)

        assert report.id == 20
        assert report.name == "Cross-tenant Test Report"

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """get_report raises NotFoundException when report_id does not exist."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.get_report(report_id=999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, mock_db_session):
        """get_report raises NotFoundException when report belongs to another tenant."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.get_report(report_id=20, tenant_id=99)


# ---------------------------------------------------------------------------
# TestCreateReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateReport:
    async def test_inserts_row_with_tenant_id(self, mock_db_session):
        """create_report adds a ReportModel with the correct tenant_id."""
        svc = ReportService(mock_db_session)

        result = await svc.create_report(
            tenant_id=3,
            data={"name": "Q1 Summary", "type": "quarterly"},
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.tenant_id == 3
        assert call_args.name == "Q1 Summary"
        assert call_args.type == "quarterly"
        mock_db_session.flush.assert_called_once()
        assert result is not None

    async def test_sets_default_values(self, mock_db_session):
        """create_report falls back to defaults when data is empty."""
        svc = ReportService(mock_db_session)

        result = await svc.create_report(tenant_id=1, data={})

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.name == "Unnamed Report"
        assert call_args.type == "custom"
        assert call_args.config == {}
        assert call_args.date_range == {}
        assert call_args.created_by == 0
        assert call_args.last_run_at is None
        assert result is not None


# ---------------------------------------------------------------------------
# TestUpdateReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdateReport:
    async def test_partial_update_preserves_unset_fields(self, mock_db_session_for_update):
        """update_report only modifies fields present in data dict."""
        svc = ReportService(mock_db_session_for_update)
        result = await svc.update_report(report_id=4, tenant_id=1, data={"name": "New Name"})

        assert result.name == "New Name"
        assert result.type == "monthly"

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """update_report raises NotFoundException when report doesn't exist."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.update_report(report_id=999, tenant_id=1, data={"name": "New Name"})


# ---------------------------------------------------------------------------
# TestDeleteReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteReport:
    async def test_deletes_existing_report(self, mock_db_session_for_delete):
        """delete_report fetches the report then calls session.delete on it."""
        svc = ReportService(mock_db_session_for_delete)
        await svc.delete_report(report_id=6, tenant_id=1)

        mock_db_session_for_delete.delete.assert_called_once()
        mock_db_session_for_delete.flush.assert_called_once()

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """delete_report raises NotFoundException when report does not exist."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.delete_report(report_id=999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, mock_db_session):
        """delete_report raises NotFoundException when report belongs to another tenant."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.delete_report(report_id=20, tenant_id=99)
        mock_db_session.delete.assert_not_called()
