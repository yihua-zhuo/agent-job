"""Tests for ImportExportService.

The DB-backed paths use a mocked AsyncSession so the test file can run without a
real Postgres. The service's behavior is exercised end-to-end (parse → validate
→ session.add/commit, or session.execute → format) but every DB call is a
no-op against the mock.
"""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure src/ is on sys.path
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest

from services.import_export_service import ImportExportService


@pytest.fixture
def mock_session():
    """AsyncMock session that no-ops add/commit and returns empty result rows."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # session.execute() -> result.scalars().all() == []  AND  result.scalar() == 0
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    empty_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=empty_result)
    return session


@pytest.fixture
def tenant_id() -> int:
    return 1


class TestImportExportServiceInit:
    """Test service instantiation and constants."""

    def test_service_instantiates(self):
        svc = ImportExportService()
        assert svc is not None

    def test_format_constants(self):
        assert ImportExportService.FORMAT_CSV == "csv"
        assert ImportExportService.FORMAT_EXCEL == "excel"
        assert ImportExportService.FORMAT_JSON == "json"
        assert ImportExportService.FORMAT_PDF == "pdf"

    def test_required_fields_configured(self):
        svc = ImportExportService()
        assert "customer" in svc.required_fields
        assert "opportunity" in svc.required_fields
        assert "lead" in svc.required_fields
        assert svc.required_fields["customer"] == ["name", "email", "phone"]


class TestValidationHelpers:
    """Test internal validation methods."""

    def test_valid_email(self):
        svc = ImportExportService()
        assert svc._is_valid_email("user@example.com") is True
        assert svc._is_valid_email("test@domain.co.uk") is True
        assert svc._is_valid_email("not-an-email") is False
        assert svc._is_valid_email("") is False

    def test_valid_phone(self):
        svc = ImportExportService()
        assert svc._is_valid_phone("13812345678") is True
        assert svc._is_valid_phone("19912345678") is True
        assert svc._is_valid_phone("1234567890") is False   # too short
        assert svc._is_valid_phone("123456789012") is False   # too long
        assert svc._is_valid_phone("") is False

    def test_valid_number(self):
        svc = ImportExportService()
        assert svc._is_valid_number("100") is True
        assert svc._is_valid_number("99.5") is True
        assert svc._is_valid_number("abc") is False
        assert svc._is_valid_number(None) is False


class TestValidateImportData:
    """Test import data validation."""

    def test_validate_good_customer_data(self):
        svc = ImportExportService()
        data = [
            {"name": "Acme Corp", "email": "contact@acme.com", "phone": "13812345678"},
            {"name": "Beta Ltd", "email": "info@beta.com", "phone": "13912345678"},
        ]
        result = svc.validate_import_data(data, "customer")
        assert result["errors"] == []

    def test_validate_missing_required_field(self):
        svc = ImportExportService()
        data = [{"name": "Acme Corp", "email": "contact@acme.com"}]  # missing phone
        result = svc.validate_import_data(data, "customer")
        assert len(result["errors"]) > 0

    def test_validate_empty_data(self):
        svc = ImportExportService()
        result = svc.validate_import_data([], "customer")
        assert result["errors"] == ["数据为空"]

    def test_validate_invalid_email_format(self):
        svc = ImportExportService()
        data = [{"name": "Bad Email Co", "email": "not-an-email", "phone": "13812345678"}]
        result = svc.validate_import_data(data, "customer")
        assert any("格式不正确" in e for e in result["errors"])

    def test_validate_duplicate_entry(self):
        svc = ImportExportService()
        data = [
            {"name": "Acme", "email": "same@email.com", "phone": "13812345678"},
            {"name": "Beta", "email": "same@email.com", "phone": "13912345678"},
        ]
        result = svc.validate_import_data(data, "customer")
        assert any("数据重复" in e for e in result["errors"])

    def test_validate_unknown_entity_type(self):
        svc = ImportExportService()
        data = [{"name": "Test"}]
        result = svc.validate_import_data(data, "unknown_type")
        # No required fields for unknown type, so no errors
        assert result["errors"] == []


# DB-backed paths — session is mocked via the `mock_session` fixture.


class TestImportCustomers:
    """Customer import — session writes are mocked."""

    @pytest.mark.asyncio
    async def test_import_customers_from_csv(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        csv_content = (
            "name,email,phone,company\n"
            "Acme Corp,contact@acme.com,13812345678,Acme Inc\n"
            "Beta Ltd,info@beta.com,13912345678,Beta Corp\n"
        )
        result = await svc.import_customers(
            file_data=csv_content.encode("utf-8"),
            file_format="csv",
            tenant_id=tenant_id,
            owner_id=1,
        )
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        # Service should add one row per record and commit once.
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_customers_from_json(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        json_content = json.dumps({
            "customers": [{"name": "Gamma Co", "email": "hello@gamma.com", "phone": "13712345678"}]
        }).encode("utf-8")
        result = await svc.import_customers(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1
        assert result["error_count"] == 0
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_customers_unsupported_format(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        result = await svc.import_customers(
            file_data=b"some data", file_format="xml", tenant_id=tenant_id,
        )
        assert result["success_count"] == 0
        assert result["error_count"] == 1
        assert "不支持" in result["errors"][0]
        # Parse failure: no DB writes should have happened.
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_awaited()


class TestImportOpportunities:
    """Opportunity import — session writes are mocked."""

    @pytest.mark.asyncio
    async def test_import_opportunities_from_json(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        json_content = json.dumps({
            "opportunities": [{"name": "Server Deal", "customer_id": 1, "amount": "50000", "stage": "proposal"}]
        }).encode("utf-8")
        result = await svc.import_opportunities(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1
        mock_session.commit.assert_awaited_once()


class TestImportLeads:
    """Lead import — session writes are mocked."""

    @pytest.mark.asyncio
    async def test_import_leads(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        json_content = json.dumps({
            "leads": [
                {"name": "Alice", "email": "alice@startup.io", "phone": "13612345678", "source": "website"},
                {"name": "Bob", "email": "bob@corp.com", "phone": "13512345678", "source": "referral"},
            ]
        }).encode("utf-8")
        result = await svc.import_leads(
            file_data=json_content, file_format="json", tenant_id=tenant_id,
        )
        assert result["success_count"] == 2
        assert mock_session.add.call_count == 2


class TestExportData:
    """Export — session.execute is mocked to return empty rows (→ sample data)."""

    @pytest.mark.asyncio
    async def test_export_customers_json(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert isinstance(parsed, list)
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_opportunities_json(self, mock_session, tenant_id):
        svc = ImportExportService(mock_session)
        data = await svc.export_opportunities(filters={}, file_format="json", tenant_id=tenant_id)
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert isinstance(parsed, list)
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_customers_returns_db_rows_when_present(self, mock_session, tenant_id):
        """When session.execute returns rows, export uses them instead of sample data."""
        # NOTE: MagicMock's `name=` kwarg sets the mock's repr name, not a `name`
        # attribute — must assign it separately.
        fake_customer = MagicMock(
            id=42, email="test@test.com",
            phone="13700000000", company="TestCorp", status="lead",
        )
        fake_customer.name = "Test Co"
        result = MagicMock()
        result.scalars.return_value.all.return_value = [fake_customer]
        mock_session.execute = AsyncMock(return_value=result)

        svc = ImportExportService(mock_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        parsed = json.loads(data.decode("utf-8"))
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Test Co"

    @pytest.mark.asyncio
    async def test_export_customers_falls_back_to_sample_when_empty(self, mock_session, tenant_id):
        """No DB rows → service returns hardcoded sample data."""
        svc = ImportExportService(mock_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=99999)
        parsed = json.loads(data.decode("utf-8"))
        assert len(parsed) == 2
        assert all(r["name"] in ("张三", "李四") for r in parsed)


class TestExportReport:
    """Report export — session.execute is mocked."""

    @pytest.mark.asyncio
    async def test_export_report_json(self, mock_session):
        svc = ImportExportService(mock_session)
        data = await svc.export_report(
            report_type="monthly_sales",
            date_range={"start": "2024-01-01", "end": "2024-01-31"},
            file_format="json",
        )
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["report_type"] == "monthly_sales"
        assert "summary" in parsed
