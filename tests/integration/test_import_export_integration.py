"""Integration tests for ImportExportService.

Helper-only tests (validation, format constants) need no DB and stay as plain
pytest functions. Everything that touches `session.add` / `session.execute`
runs against the real Postgres test DB via the `async_session` fixture from
`tests/integration/conftest.py`, in line with the CLAUDE.md rule that
integration tests must use real database fixtures, not mocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path (Makefile already exports PYTHONPATH=src; this
# guards direct `pytest tests/integration/...` invocations).
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest
from sqlalchemy import select

from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from services.import_export_service import ImportExportService


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


async def _count_customers(session, tenant_id: int) -> int:
    result = await session.execute(
        select(CustomerModel).where(CustomerModel.tenant_id == tenant_id)
    )
    return len(result.scalars().all())


async def _count_opportunities(session, tenant_id: int) -> int:
    result = await session.execute(
        select(OpportunityModel).where(OpportunityModel.tenant_id == tenant_id)
    )
    return len(result.scalars().all())


# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers — no session needed
# ──────────────────────────────────────────────────────────────────────────────


class TestImportExportServiceInit:
    """Service instantiation and constants."""

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
    """Internal validation methods."""

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
        assert svc._is_valid_phone("123456789012") is False  # too long
        assert svc._is_valid_phone("") is False

    def test_valid_number(self):
        svc = ImportExportService()
        assert svc._is_valid_number("100") is True
        assert svc._is_valid_number("99.5") is True
        assert svc._is_valid_number("abc") is False
        assert svc._is_valid_number(None) is False


class TestValidateImportData:
    """Input validation."""

    def test_validate_good_customer_data(self):
        svc = ImportExportService()
        data = [
            {"name": "Acme Corp", "email": "contact@acme.com", "phone": "13812345678"},
            {"name": "Beta Ltd", "email": "info@beta.com", "phone": "13912345678"},
        ]
        assert svc.validate_import_data(data, "customer")["errors"] == []

    def test_validate_missing_required_field(self):
        svc = ImportExportService()
        data = [{"name": "Acme Corp", "email": "contact@acme.com"}]  # missing phone
        assert len(svc.validate_import_data(data, "customer")["errors"]) > 0

    def test_validate_empty_data(self):
        svc = ImportExportService()
        assert svc.validate_import_data([], "customer")["errors"] == ["数据为空"]

    def test_validate_invalid_email_format(self):
        svc = ImportExportService()
        data = [{"name": "Bad Email Co", "email": "not-an-email", "phone": "13812345678"}]
        errors = svc.validate_import_data(data, "customer")["errors"]
        assert any("格式不正确" in e for e in errors)

    def test_validate_duplicate_entry(self):
        svc = ImportExportService()
        data = [
            {"name": "Acme", "email": "same@email.com", "phone": "13812345678"},
            {"name": "Beta", "email": "same@email.com", "phone": "13912345678"},
        ]
        errors = svc.validate_import_data(data, "customer")["errors"]
        assert any("数据重复" in e for e in errors)

    def test_validate_unknown_entity_type(self):
        svc = ImportExportService()
        assert svc.validate_import_data([{"name": "Test"}], "unknown_type")["errors"] == []


# ──────────────────────────────────────────────────────────────────────────────
# DB-backed tests — real Postgres via async_session
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestImportCustomers:
    """Customer import — writes go to the real test DB."""

    async def test_import_customers_from_csv(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        csv_content = (
            "name,email,phone,company\n"
            "Acme Corp,contact@acme.com,13812345678,Acme Inc\n"
            "Beta Ltd,info@beta.com,13912345678,Beta Corp\n"
        ).encode("utf-8")
        result = await svc.import_customers(
            file_data=csv_content, file_format="csv",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert await _count_customers(async_session, tenant_id) == 2

    async def test_import_customers_from_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        json_content = json.dumps({
            "customers": [
                {"name": "Gamma Co", "email": "hello@gamma.com", "phone": "13712345678"}
            ]
        }).encode("utf-8")
        result = await svc.import_customers(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert await _count_customers(async_session, tenant_id) == 1

    async def test_import_customers_unsupported_format(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        result = await svc.import_customers(
            file_data=b"some data", file_format="xml", tenant_id=tenant_id,
        )
        assert result["success_count"] == 0
        assert result["error_count"] == 1
        assert "不支持" in result["errors"][0]
        # Parse failure → no rows should have been written.
        assert await _count_customers(async_session, tenant_id) == 0


@pytest.mark.integration
class TestImportOpportunities:
    """Opportunity import — writes go to the real test DB."""

    async def test_import_opportunities_from_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        json_content = json.dumps({
            "opportunities": [
                {"name": "Server Deal", "customer_id": 1, "amount": "50000", "stage": "proposal"}
            ]
        }).encode("utf-8")
        result = await svc.import_opportunities(
            file_data=json_content, file_format="json",
            tenant_id=tenant_id, owner_id=1,
        )
        assert result["success_count"] == 1
        assert await _count_opportunities(async_session, tenant_id) == 1


@pytest.mark.integration
class TestImportLeads:
    """Lead import — leads are persisted as CustomerModel rows with status='lead'."""

    async def test_import_leads(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        json_content = json.dumps({
            "leads": [
                {"name": "Alice", "email": "alice@startup.io", "phone": "13612345678", "source": "website"},
                {"name": "Bob",   "email": "bob@corp.com",     "phone": "13512345678", "source": "referral"},
            ]
        }).encode("utf-8")
        result = await svc.import_leads(
            file_data=json_content, file_format="json", tenant_id=tenant_id,
        )
        assert result["success_count"] == 2
        assert await _count_customers(async_session, tenant_id) == 2


@pytest.mark.integration
class TestExportData:
    """Export — reads come from the real test DB."""

    async def test_export_customers_returns_db_rows(self, db_schema, tenant_id, async_session):
        # Seed one customer directly via the ORM so the export path has a row to find.
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        async_session.add(
            CustomerModel(
                tenant_id=tenant_id,
                name="Test Co",
                email="test@test.com",
                phone="13700000000",
                company="TestCorp",
                status="lead",
                owner_id=1,
                tags=[],
                created_at=now,
                updated_at=now,
            )
        )
        await async_session.flush()

        svc = ImportExportService(async_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        parsed = json.loads(data.decode("utf-8"))
        names = {row["name"] for row in parsed}
        assert "Test Co" in names

    async def test_export_customers_falls_back_to_sample_when_empty(
        self, db_schema, tenant_id, async_session
    ):
        # No seeded rows for this tenant → service returns the hardcoded sample data.
        svc = ImportExportService(async_session)
        data = await svc.export_customers(filters={}, file_format="json", tenant_id=tenant_id)
        parsed = json.loads(data.decode("utf-8"))
        assert all(row["name"] in ("张三", "李四") for row in parsed)

    async def test_export_opportunities_json(self, db_schema, tenant_id, async_session):
        svc = ImportExportService(async_session)
        data = await svc.export_opportunities(filters={}, file_format="json", tenant_id=tenant_id)
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert isinstance(parsed, list)


@pytest.mark.integration
class TestExportReport:
    """Report export — synthetic data, but uses real session."""

    async def test_export_report_json(self, db_schema, tenant_id, async_session):
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
