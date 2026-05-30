"""Unit tests for ReportService CRUD methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.report_service import ReportService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_result(rows=None, scalar_one_val=None, scalar_one_or_none_val=None):
    """Build a MockResult wired to scalars()."""
    rows = rows or []
    result = MagicMock()
    result.scalars = MagicMock(
        return_value=MagicMock(
            all=MagicMock(return_value=rows),
            first=MagicMock(return_value=rows[0] if rows else None),
        )
    )
    result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none_val)
    result.scalar_one = MagicMock(return_value=scalar_one_val)
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Inline mock session with no handlers — tests wire execute() per case."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# TestListReports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListReports:
    async def test_returns_reports_and_total(self, mock_db_session):
        """list_reports returns (list, total) for a tenant."""
        mock_result = _make_mock_result(rows=[MagicMock(id=1), MagicMock(id=2)], scalar_one_val=2)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1)

        assert total == 2
        assert len(reports) == 2
        assert mock_db_session.execute.call_count == 2

    async def test_empty_list_returns_zero_total(self, mock_db_session):
        """Empty tenant returns empty list and zero total."""
        mock_result = _make_mock_result(rows=[], scalar_one_val=0)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1)

        assert total == 0
        assert reports == []

    async def test_applies_limit_and_offset(self, mock_db_session):
        """list_reports applies LIMIT/OFFSET based on page and page_size."""
        mock_result = _make_mock_result(rows=[MagicMock(id=3)], scalar_one_val=5)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        svc = ReportService(mock_db_session)
        reports, total = await svc.list_reports(tenant_id=1, page=2, page_size=2)

        assert total == 5
        assert len(reports) == 1
        # page=2, page_size=2 → offset=(2-1)*2=2 — reflected in the compiled query
        calls = mock_db_session.execute.await_args_list
        select_call = calls[1]
        compiled = select_call.args[0].compile(compile_kwargs={"literal_binds": True})
        assert "limit" in str(compiled).lower()
        assert "offset" in str(compiled).lower()


# ---------------------------------------------------------------------------
# TestGetReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetReport:
    async def test_returns_report_for_valid_id(self, mock_db_session):
        """get_report returns the report when it exists for the tenant."""
        mock_report = MagicMock()
        mock_report.id = 5
        mock_report.name = "Sales Report"
        mock_report.tenant_id = 1
        mock_result = _make_mock_result(scalar_one_or_none_val=mock_report)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        svc = ReportService(mock_db_session)
        report = await svc.get_report(report_id=5, tenant_id=1)

        assert report.id == 5
        assert report.name == "Sales Report"

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """get_report raises NotFoundException when report_id does not exist."""
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=None))

        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.get_report(report_id=999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, mock_db_session):
        """get_report raises NotFoundException when report belongs to another tenant."""
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=None))

        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            # tenant_id=2 doesn't own report 5 (which belongs to tenant 1)
            await svc.get_report(report_id=5, tenant_id=2)


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
    async def test_partial_update_preserves_unset_fields(self, mock_db_session):
        """update_report only modifies fields present in data dict."""
        existing = MagicMock(id=4, name="Old Name", type="monthly", config={}, date_range={}, last_run_at=None)
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=existing))
        mock_db_session.refresh = AsyncMock()

        svc = ReportService(mock_db_session)
        result = await svc.update_report(report_id=4, tenant_id=1, data={"name": "New Name"})

        assert existing.name == "New Name"
        # type should be unchanged
        assert existing.type == "monthly"
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(existing)
        assert result is existing

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """update_report raises NotFoundException when report doesn't exist."""
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=None))

        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.update_report(report_id=999, tenant_id=1, data={"name": "New Name"})


# ---------------------------------------------------------------------------
# TestDeleteReport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteReport:
    async def test_deletes_existing_report(self, mock_db_session):
        """delete_report executes DELETE and flushes when report exists."""
        mock_result = _make_mock_result(scalar_one_or_none_val=MagicMock(id=6))
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        svc = ReportService(mock_db_session)
        await svc.delete_report(report_id=6, tenant_id=1)

        # Should have called execute twice: once to verify existence, once to delete
        assert mock_db_session.execute.call_count == 2
        mock_db_session.flush.assert_called_once()

        # Verify the second execute call is a DELETE with correct WHERE clause
        delete_call = mock_db_session.execute.await_args_list[1]
        sql_str = str(delete_call.args[0]).lower()
        assert "delete" in sql_str
        assert "id" in sql_str or "report" in sql_str  # DELETE targets report table

    async def test_raises_not_found_for_missing_id(self, mock_db_session):
        """delete_report raises NotFoundException when report doesn't exist."""
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=None))

        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.delete_report(report_id=999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, mock_db_session):
        """delete_report raises NotFoundException when report belongs to another tenant."""
        mock_db_session.execute = AsyncMock(return_value=_make_mock_result(scalar_one_or_none_val=None))

        svc = ReportService(mock_db_session)
        with pytest.raises(NotFoundException, match="Report"):
            await svc.delete_report(report_id=5, tenant_id=99)
