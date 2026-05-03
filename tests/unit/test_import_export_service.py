"""Unit tests for ImportExportService."""
import json
import pytest
from services.import_export_service import ImportExportService


@pytest.fixture
def import_export_service(mock_db_session):
    return ImportExportService(mock_db_session)


@pytest.fixture
def sample_customer_data(mock_db_session):
    return [
        {"name": "Zhang San", "email": "zhangsan@example.com", "phone": "13800138000", "company": "Company A"},
        {"name": "Li Si", "email": "lisi@example.com", "phone": "13900139000", "company": "Company B"},
    ]


@pytest.fixture
def sample_opportunity_data(mock_db_session):
    return [
        {"name": "Project A", "customer_id": 1, "amount": 100000, "stage": "proposal"},
        {"name": "Project B", "customer_id": 2, "amount": 200000, "stage": "negotiation"},
    ]


@pytest.fixture
def sample_lead_data(mock_db_session):
    return [
        {"name": "Wang Wu", "email": "wangwu@example.com", "source": "website"},
        {"name": "Zhao Liu", "email": "zhaoliu@example.com", "source": "event"},
    ]


@pytest.mark.asyncio
class TestImportExportService:







    async def test_export_report_json(self, import_export_service):
        result = await import_export_service.export_report(
            report_type="monthly",
            date_range={"start": "2024-01", "end": "2024-12"},
            file_format="json",
        )
        assert isinstance(result, bytes)

    async def test_export_report_pdf(self, import_export_service):
        result = await import_export_service.export_report(
            report_type="sales",
            date_range={"start": "2024-01", "end": "2024-12"},
            file_format="pdf",
        )
        assert isinstance(result, bytes)

    async def test_generate_pdf_report(self, import_export_service):
        report_data = {
            "generated_at": "2024-01-01T00:00:00",
            "summary": {"total": 100, "revenue": 5000000},
            "details": [{"month": "2024-01", "revenue": 400000}],
        }
        result = await import_export_service.generate_pdf_report(report_data, "Test Report")
        assert isinstance(result, bytes)
        assert len(result) > 0


    async def test_import_customers_unsupported_format(self, import_export_service):
        result = await import_export_service.import_customers(b"data", "xml")
        assert result["success_count"] == 0
        assert result["error_count"] >= 1

    async def test_import_customers_invalid_json(self, import_export_service):
        result = await import_export_service.import_customers(b"not valid json", "json")
        assert result["success_count"] == 0
        assert result["error_count"] >= 1











    async def test_is_valid_email_various_formats(self, import_export_service):
        assert import_export_service._is_valid_email("test@example.com") is True
        assert import_export_service._is_valid_email("user.name+tag@example.co.uk") is True
        assert import_export_service._is_valid_email("invalid") is False
        assert import_export_service._is_valid_email("@example.com") is False
        assert import_export_service._is_valid_email("user@") is False

    async def test_is_valid_phone_various_formats(self, import_export_service):
        assert import_export_service._is_valid_phone("13800138000") is True
        assert import_export_service._is_valid_phone("19912345678") is True
        assert import_export_service._is_valid_phone("1234567890") is False
        assert import_export_service._is_valid_phone("abc12345678") is False

    async def test_is_valid_number(self, import_export_service):
        assert import_export_service._is_valid_number(100) is True
        assert import_export_service._is_valid_number(100.5) is True
        assert import_export_service._is_valid_number("100") is True
        assert import_export_service._is_valid_number("abc") is False

    async def test_export_data_unsupported_format(self, import_export_service):
        with pytest.raises(ValueError, match="不支持"):
            await import_export_service._export_data([], {}, "unsupported")

    async def test_generate_pdf_report_minimal(self, import_export_service):
        report_data = {"summary": {"total": 100}, "details": []}
        result = await import_export_service.generate_pdf_report(report_data, "Minimal")
        assert isinstance(result, bytes)

