"""Unit tests for ReportService CRUD methods."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect as sqla_inspect

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.report_service import ReportService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.reports import make_report_handler, make_schedule_handler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Mock session with 25 seeded reports (ids 10-34) plus id=20 for lookup."""
    state = MockState()
    state.opaque["reports"] = {"records": {}, "next_id": 35}
    for rid in range(10, 35):
        state.opaque["reports"]["records"][rid] = {
            "id": rid, "tenant_id": 1, "name": f"Report {rid}",
            "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
            "last_run_at": None, "created_at": None,
        }
    # id=20 is the standalone record used for single-record lookup tests
    state.opaque["reports"]["records"][20] = {
        "id": 20, "tenant_id": 1, "name": "Isolated Tenant Test Report",
        "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    # Seed a tenant-2 report to verify cross-tenant isolation in list_reports
    state.opaque["reports"]["records"][50] = {
        "id": 50, "tenant_id": 2, "name": "Tenant 2 Report",
        "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)], state=state)


@pytest.fixture
def mock_db_session_for_update():
    """Mock session for update tests with a pre-seeded report (id=4)."""
    state = MockState()
    state.opaque["reports"] = {"records": {}, "next_id": 21}
    state.opaque["reports"]["records"][4] = {
        "id": 4, "tenant_id": 1, "name": "Old Name", "type": "monthly",
        "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)], state=state)


@pytest.fixture
def mock_db_session_for_delete():
    """Mock session for delete tests with a pre-seeded report (id=6)."""
    state = MockState()
    state.opaque["reports"] = {"records": {}, "next_id": 21}
    state.opaque["reports"]["records"][6] = {
        "id": 6, "tenant_id": 1, "name": "To Delete", "type": "custom",
        "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session([make_report_handler(state)], state=state)


# ---------------------------------------------------------------------------
# TestListReports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListReports:
    async def test_returns_reports_and_total(self, mock_db_session):
        """list_reports returns (list, total) for a tenant."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1)

        # 25 records are seeded (ids 10-34); id=20 is among them, so total=25.
        # Default page_size=20 means the SELECT is capped at 20 even though 25 exist.
        assert total == 25
        assert len(reports) == 20
        assert mock_db_session.execute.call_count == 2
        # Verify both calls are SELECT statements (count + data fetch).
        calls = mock_db_session.execute.call_args_list
        for call in calls:
            assert sqla_inspect(call.args[0]).is_select

    async def test_empty_list_returns_zero_total(self, mock_db_session):
        """Empty tenant returns empty list and zero total."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=999)

        assert total == 0
        # Explicitly assert zero records — the 'all' assertion below is
        # vacuously true on empty lists, so split into two assertions.
        # Tenant isolation is implicitly verified: a non-zero total would
        # mean records leaked across tenant scope.
        assert reports == []

    async def test_applies_limit_and_offset(self, mock_db_session):
        """list_reports applies LIMIT/OFFSET based on page and page_size."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1, page=2, page_size=2)

        assert total == 25
        # Verify exactly two calls (count + paginated fetch).
        assert mock_db_session.execute.call_count == 2
        calls = mock_db_session.execute.call_args_list
        # First call must be the COUNT query.
        assert sqla_inspect(calls[0].args[0]).is_select
        assert "count(" in str(calls[0].args[0]).lower()
        # Second call is the paginated SELECT with LIMIT=2 OFFSET=2.
        select_call_args = calls[1].args
        assert len(select_call_args) >= 1
        stmt = select_call_args[0]
        insp = sqla_inspect(stmt)
        assert insp.is_select
        assert insp._limit == 2
        assert insp._offset == 2

    async def test_enforces_limit_clause(self, mock_db_session):
        """list_reports(page=1, page_size=20) returns exactly 20 items when >20 exist."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1, page=1, page_size=20)

        assert total == 25
        assert len(reports) == 20

    async def test_excludes_other_tenant_reports(self, mock_db_session):
        """list_reports(tenant_id=1) excludes reports seeded for tenant_id=2."""
        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1)

        # id=50 belongs to tenant 2 and must not appear in tenant 1 results.
        returned_ids = {r.id for r in reports}
        assert 50 not in returned_ids


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
        assert report.tenant_id == 1
        assert report.name == "Isolated Tenant Test Report"
        # Verify serialized output has the expected keys.
        d = report.to_dict()
        assert set(d.keys()) >= {"id", "name", "tenant_id", "type", "config", "date_range"}

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

    async def test_tenant_isolation_explicit(self, mock_db_session):
        """A record seeded for tenant_id=1 is invisible to tenant_id=2."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.get_report(report_id=20, tenant_id=2)


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
        # Verify pre-condition: type is already 'monthly' before the update.
        rec_before = await svc.get_report(report_id=4, tenant_id=1)
        assert rec_before.type == "monthly"
        result = await svc.update_report(report_id=4, tenant_id=1, data={"name": "New Name"})

        assert result.name == "New Name"
        assert result.type == "monthly"
        assert result.last_run_at is None  # must not be overwritten by partial update

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """update_report raises NotFoundException when report doesn't exist."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.update_report(report_id=999, tenant_id=1, data={"name": "New Name"})

    async def test_raises_not_found_for_wrong_tenant(self, mock_db_session):
        """update_report raises NotFoundException when report belongs to a different tenant."""
        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.update_report(report_id=20, tenant_id=99, data={"name": "Hijack Attempt"})


# ---------------------------------------------------------------------------
# TestDeleteReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteReport:
    async def test_deletes_existing_report(self, mock_db_session_for_delete):
        """delete_report removes the row and calls session.delete with the right args."""
        svc = ReportService(mock_db_session_for_delete)
        await svc.delete_report(report_id=6, tenant_id=1)

        assert mock_db_session_for_delete.delete.call_count == 1
        mock_db_session_for_delete.delete.assert_called_once()
        mock_db_session_for_delete.flush.assert_called_once()
        # Verify the deleted object had id=6 for the correct tenant.
        deleted_obj = mock_db_session_for_delete.delete.call_args[0][0]
        assert deleted_obj.id == 6
        assert deleted_obj.tenant_id == 1

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


# ---------------------------------------------------------------------------
# TestScheduleReport
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session_for_schedule():
    """Mock session for schedule_report tests with both report and schedule handlers."""
    state = MockState()
    state.opaque["reports"] = {"records": {}, "next_id": 1}
    state.opaque["report_schedules"] = {"records": {}, "next_id": 1}
    state.opaque["reports"]["records"][7] = {
        "id": 7, "tenant_id": 1, "name": "Report to Schedule",
        "type": "custom", "config": {}, "date_range": {}, "created_by": 0,
        "last_run_at": None, "created_at": None,
    }
    return make_mock_session(
        [make_report_handler(state), make_schedule_handler(state)], state=state
    )


@pytest.mark.asyncio
class TestScheduleReport:
    async def test_upsert_creates_schedule(self, mock_db_session_for_schedule):
        """schedule_report inserts a new schedule when none exists for (report_id, tenant_id)."""
        svc = ReportService(mock_db_session_for_schedule)
        result = await svc.schedule_report(
            report_id=7,
            schedule={"frequency": "daily"},
            tenant_id=1,
        )
        mock_db_session_for_schedule.add.assert_called()
        mock_db_session_for_schedule.flush.assert_called()
        call_args = mock_db_session_for_schedule.add.call_args[0][0]
        assert call_args.report_id == 7
        assert call_args.tenant_id == 1
        assert call_args.schedule == {"frequency": "daily"}
        assert call_args.active is True

    async def test_upsert_updates_existing_schedule(self, mock_db_session_for_schedule):
        """schedule_report updates the schedule when one already exists for (report_id, tenant_id)."""
        svc = ReportService(mock_db_session_for_schedule)
        # First call — creates
        await svc.schedule_report(report_id=7, schedule={"frequency": "daily"}, tenant_id=1)
        # Reset mock state from the first call
        mock_db_session_for_schedule.add.reset_mock()
        mock_db_session_for_schedule.flush.reset_mock()
        # Second call — updates the existing record
        result = await svc.schedule_report(
            report_id=7,
            schedule={"frequency": "weekly"},
            tenant_id=1,
        )
        # A new ReportScheduleModel should NOT be added on the update path
        added_schedules = [
            c for c in mock_db_session_for_schedule.add.call_args_list
            if c[0][0].__class__.__name__ == "ReportScheduleModel"
        ]
        assert len(added_schedules) == 0
        # The schedule field was updated to the new value
        assert result.schedule == {"frequency": "weekly"}

    async def test_creates_schedule_for_nonexistent_report(self, mock_db_session_for_schedule):
        """schedule_report inserts a schedule even if the report row doesn't exist in reports table.

        The service does not validate report existence — it only upserts by (report_id, tenant_id).
        """
        svc = ReportService(mock_db_session_for_schedule)
        result = await svc.schedule_report(report_id=9999, schedule={"frequency": "monthly"}, tenant_id=1)
        mock_db_session_for_schedule.add.assert_called()
        call_args = mock_db_session_for_schedule.add.call_args[0][0]
        assert call_args.report_id == 9999
        assert call_args.tenant_id == 1


# ---------------------------------------------------------------------------
# TestReportGenerators (stubs)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestReportGenerators:
    async def test_generate_pdf_returns_valid_structure(self):
        """generate_pdf_report returns the expected stub response shape."""
        svc = ReportService(MagicMock())
        result = await svc.generate_pdf_report(title="Test PDF", report_type="custom")
        assert result["status"] == "generated"
        assert result["format"] == "pdf"
        assert result["filename"].endswith(".pdf")
        assert "_is_stub" in result

    async def test_generate_excel_returns_valid_structure(self):
        """generate_excel_report returns the expected stub response shape."""
        svc = ReportService(MagicMock())
        result = await svc.generate_excel_report(tenant_id=0, title="Test Excel", report_type="custom")
        assert result["status"] == "generated"
        assert result["format"] == "excel"
        assert result["filename"].endswith(".xlsx")


# ---------------------------------------------------------------------------
# TestExportToCsv
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExportToCsv:
    async def test_safe_filename_rejects_absolute_path(self):
        """_safe_export_filename rejects absolute paths to prevent path traversal."""
        svc = ReportService(MagicMock())
        result = await svc.export_to_csv(
            data=[{"a": 1}],
            filename="/etc/passwd",
        )
        assert result["filename"].startswith("export-")
        assert result["filename"].endswith(".csv")
        assert result["filename"] != "/etc/passwd"

    async def test_safe_filename_rejects_parent_reference(self):
        """_safe_export_filename rejects '..' to prevent directory traversal."""
        svc = ReportService(MagicMock())
        result = await svc.export_to_csv(
            data=[{"a": 1}],
            filename="../../../etc/passwd",
        )
        assert result["filename"].startswith("export-")
        assert result["filename"].endswith(".csv")

    async def test_safe_filename_accepts_plain_name(self):
        """_safe_export_filename accepts a plain filename without modification."""
        svc = ReportService(MagicMock())
        result = await svc.export_to_csv(
            data=[{"a": 1}],
            filename="my-report.csv",
        )
        assert result["filename"] == "my-report.csv"

    async def test_raises_when_no_data(self):
        """export_to_csv raises ValidationException when data is empty."""
        svc = ReportService(MagicMock())
        with pytest.raises(ValidationException, match="No data"):
            await svc.export_to_csv(data=[])
