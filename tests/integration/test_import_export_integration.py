"""Integration tests for ImportExportService - tests data import/export in CSV/JSON/Excel formats."""
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest

from services.import_export_service import ImportExportService


class TestImportExportServiceInit:
    """Test service instantiation and constants."""

    def test_service_instantiates(self):
        svc = ImportExportService(None)
        assert svc is not None

    def test_format_constants(self):
        assert ImportExportService.FORMAT_CSV == "csv"
        assert ImportExportService.FORMAT_EXCEL == "excel"
        assert ImportExportService.FORMAT_JSON == "json"
        assert ImportExportService.FORMAT_PDF == "pdf"

    def test_required_fields_configured(self):
        svc = ImportExportService(None)
        assert "customer" in svc.required_fields
        assert "opportunity" in svc.required_fields
        assert "lead" in svc.required_fields
        assert svc.required_fields["customer"] == ["name", "email", "phone"]


class TestValidationHelpers:
    """Test internal validation methods."""

    def test_valid_email(self):
        svc = ImportExportService(None)
        assert svc._is_valid_email("user@example.com") is True
        assert svc._is_valid_email("test@domain.co.uk") is True
        assert svc._is_valid_email("not-an-email") is False
        assert svc._is_valid_email("") is False

    def test_valid_phone(self):
        svc = ImportExportService(None)
        assert svc._is_valid_phone("13812345678") is True
        assert svc._is_valid_phone("19912345678") is True
        assert svc._is_valid_phone("1234567890") is False   # too short
        assert svc._is_valid_phone("123456789012") is False   # too long
        assert svc._is_valid_phone("") is False

    def test_valid_number(self):
        svc = ImportExportService(None)
        assert svc._is_valid_number("100") is True
        assert svc._is_valid_number("99.5") is True
        assert svc._is_valid_number("abc") is False
        assert svc._is_valid_number(None) is False


class TestValidateImportData:
    """Test import data validation."""

    def test_validate_good_customer_data(self):
        svc = ImportExportService(None)
        data = [
            {"name": "Acme Corp", "email": "contact@acme.com", "phone": "13812345678"},
            {"name": "Beta Ltd", "email": "info@beta.com", "phone": "13912345678"},
        ]
        result = svc.validate_import_data(data, "customer")
        assert result["errors"] == []

    def test_validate_missing_required_field(self):
        svc = ImportExportService(None)
        data = [{"name": "Acme Corp", "email": "contact@acme.com"}]  # missing phone
        result = svc.validate_import_data(data, "customer")
        assert len(result["errors"]) > 0

    def test_validate_empty_data(self):
        svc = ImportExportService(None)
        result = svc.validate_import_data([], "customer")
        assert result["errors"] == ["数据为空"]

    def test_validate_invalid_email_format(self):
        svc = ImportExportService(None)
        data = [{"name": "Bad Email Co", "email": "not-an-email", "phone": "13812345678"}]
        result = svc.validate_import_data(data, "customer")
        assert any("格式不正确" in e for e in result["errors"])

    def test_validate_duplicate_entry(self):
        svc = ImportExportService(None)
        data = [
            {"name": "Acme", "email": "same@email.com", "phone": "13812345678"},
            {"name": "Beta", "email": "same@email.com", "phone": "13912345678"},
        ]
        result = svc.validate_import_data(data, "customer")
        assert any("数据重复" in e for e in result["errors"])

    def test_validate_unknown_entity_type(self):
        svc = ImportExportService(None)
        data = [{"name": "Test"}]
        result = svc.validate_import_data(data, "unknown_type")
        # No required fields for unknown type, so no errors
        assert result["errors"] == []


# DB-backed import/export tests.
# conftest.py rewrites DATABASE_URL (psycopg2) → asyncpg for TEST_DATABASE_URL.
# These tests use fixtures that connect to the real DB.


class TestImportCustomers:
    """Customer import via DB."""

    @pytest.mark.asyncio
    async def test_import_customers_from_csv(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
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

    @pytest.mark.asyncio
    async def test_import_customers_from_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        json_content = json.dumps({
            "customers": [{"name": "Gamma Co", "email": "hello@gamma.com", "phone": "13712345678"}]
        }).encode("utf-8")
        result = await svc.import_customers(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_import_customers_unsupported_format(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        result = await svc.import_customers(
            file_data=b"some data", file_format="xml", tenant_id=tenant_id,
        )
        assert result["success_count"] == 0
        assert result["error_count"] == 1
        assert "不支持" in result["errors"][0]


class TestImportOpportunities:
    """Opportunity import via DB."""

    @pytest.mark.asyncio
    async def test_import_opportunities_from_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        json_content = json.dumps({
            "opportunities": [{"name": "Server Deal", "customer_id": 1, "amount": "50000", "stage": "proposal"}]
        }).encode("utf-8")
        result = await svc.import_opportunities(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1


class TestImportLeads:
    """Lead import via DB."""

    @pytest.mark.asyncio
    async def test_import_leads(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
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


class TestExportData:
    """Export data via DB."""

    @pytest.mark.asyncio
    async def test_export_customers_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_export_opportunities_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        data = await svc.export_opportunities(filters={}, file_format="json", tenant_id=tenant_id)
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_export_customers_respects_tenant(self, db_schema, tenant_id, async_session):
        """Verify export only returns records for the specified tenant.

        When the DB has no rows for the queried tenant, the service returns
        hardcoded sample data (a preview feature). So we first import known
        records, then verify export returns those DB records — proving tenant
        isolation works (different tenant sees its own data, not ours).
        """
        svc = ImportExportService(async_session)

        # Import a known record for tenant_id; service auto-commits via asyncpg
        import_result = await svc.import_customers(
            file_data=b"name,email,phone,company\nTest Co,test@test.com,13700000000,TestCorp",
            file_format="csv",
            tenant_id=tenant_id,
            owner_id=1,
        )
        assert import_result["success_count"] == 1

        # Export should return the one DB record we just inserted.
        # NOTE: if the DB query returns 0 rows, the service falls back to
        # hardcoded sample data (张三/李四) regardless of tenant_id.
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        parsed = json.loads(data.decode("utf-8"))
        assert len(parsed) == 1, (
            f"expected 1 DB row, got sample data instead — "
            f"export query returned 0 rows for tenant {tenant_id}"
        )
        assert parsed[0]["name"] == "Test Co"

        # A completely different tenant_id returns no rows → sample data fallback
        data_other = await svc.export_customers(filters={}, file_format="json", tenant_id=99999)
        parsed_other = json.loads(data_other.decode("utf-8"))
        assert len(parsed_other) == 2
        assert all(r["name"] in ("张三", "李四") for r in parsed_other)


class TestExportReport:
    """Report export via DB."""

    @pytest.mark.asyncio
    async def test_export_report_json(self, db_schema, async_session):
        svc = ImportExportService(async_session)
        data = await svc.export_report(
            report_type="monthly_sales",
            date_range={"start": "2024-01-01", "end": "2024-01-31"},
            file_format="json",
        )
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["report_type"] == "monthly_sales"
        assert "summary" in parsed
