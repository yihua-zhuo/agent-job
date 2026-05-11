"""导入导出服务单元测试"""
import pytest
import json

from src.services.import_export_service import ImportExportService


@pytest.fixture
def import_export_service():
    """创建导入导出服务实例(no session — in-memory tests)"""
    return ImportExportService()


@pytest.fixture
def sample_customer_data():
    return [
        {"name": "张三", "email": "zhangsan@example.com", "phone": "13800138000", "company": "公司A"},
        {"name": "李四", "email": "lisi@example.com", "phone": "13900139000", "company": "公司B"},
    ]


@pytest.fixture
def sample_opportunity_data():
    return [
        {"name": "项目A", "customer_id": 1, "amount": 100000, "stage": "提案"},
        {"name": "项目B", "customer_id": 2, "amount": 200000, "stage": "谈判"},
    ]


@pytest.fixture
def sample_lead_data():
    return [
        {"name": "王五", "email": "wangwu@example.com", "source": "官网"},
        {"name": "赵六", "email": "zhaoliu@example.com", "source": "展会"},
    ]


class TestImportExportServiceNormal:
    async def test_import_customers_csv(self, import_export_service, sample_customer_data):
        csv_content = "name,email,phone,company\n"
        for c in sample_customer_data:
            csv_content += f"{c['name']},{c['email']},{c['phone']},{c['company']}\n"
        result = await import_export_service.import_customers(csv_content.encode('utf-8'), "csv")
        assert result["success_count"] == 2
        assert result["error_count"] == 0

    async def test_import_customers_json(self, import_export_service, sample_customer_data):
        json_content = json.dumps(sample_customer_data).encode('utf-8')
        result = await import_export_service.import_customers(json_content, "json")
        assert result["success_count"] == 2

    async def test_import_opportunities_json(self, import_export_service, sample_opportunity_data):
        json_content = json.dumps(sample_opportunity_data).encode('utf-8')
        result = await import_export_service.import_opportunities(json_content, "json")
        assert result["success_count"] == 2

    async def test_import_leads_json(self, import_export_service, sample_lead_data):
        json_content = json.dumps(sample_lead_data).encode('utf-8')
        result = await import_export_service.import_leads(json_content, "json")
        assert result["success_count"] == 2

    async def test_export_customers_csv(self, import_export_service):
        result = await import_export_service.export_customers({}, "csv")
        assert isinstance(result, bytes)
        assert len(result) > 0

    async def test_export_customers_json(self, import_export_service):
        result = await import_export_service.export_customers({}, "json")
        assert isinstance(result, bytes)
        data = json.loads(result)
        assert isinstance(data, list)

    async def test_export_opportunities_json(self, import_export_service):
        result = await import_export_service.export_opportunities({}, "json")
        assert isinstance(result, bytes)

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

    def test_generate_pdf_report(self, import_export_service):
        report_data = {
            "generated_at": "2024-01-01T00:00:00",
            "summary": {"total": 100, "revenue": 5000000},
            "details": [
                {"month": "2024-01", "revenue": 400000},
                {"month": "2024-02", "revenue": 450000},
            ],
        }
        result = import_export_service.generate_pdf_report(report_data, "测试报表")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_validate_import_data_valid(self, import_export_service, sample_customer_data):
        result = import_export_service.validate_import_data(sample_customer_data, "customer")
        assert "errors" in result
        assert len(result["errors"]) == 0


class TestImportExportServiceEdgeCases:
    async def test_import_customers_unsupported_format(self, import_export_service):
        result = await import_export_service.import_customers(b"data", "xml")
        assert result["success_count"] == 0
        assert result["error_count"] == 1
        assert "不支持" in result["errors"][0]

    async def test_import_customers_invalid_json(self, import_export_service):
        result = await import_export_service.import_customers(b"not valid json", "json")
        assert result["success_count"] == 0
        assert result["error_count"] == 1

    def test_import_customers_missing_required_field(self, import_export_service):
        data = [{"name": "张三", "email": "test@example.com"}]
        result = import_export_service.validate_import_data(data, "customer")
        assert len(result["errors"]) > 0

    def test_import_customers_invalid_email(self, import_export_service):
        data = [{"name": "张三", "email": "invalid-email", "phone": "13800138000"}]
        result = import_export_service.validate_import_data(data, "customer")
        assert len(result["errors"]) > 0

    def test_import_customers_invalid_phone(self, import_export_service):
        data = [{"name": "张三", "email": "test@example.com", "phone": "12345"}]
        result = import_export_service.validate_import_data(data, "customer")
        assert len(result["errors"]) > 0

    def test_import_customers_empty_data(self, import_export_service):
        result = import_export_service.validate_import_data([], "customer")
        assert "数据为空" in result["errors"][0]

    def test_import_customers_duplicate_entries(self, import_export_service):
        data = [
            {"name": "张三", "email": "test@example.com", "phone": "13800138000"},
            {"name": "张三2", "email": "test@example.com", "phone": "13900139000"},
        ]
        result = import_export_service.validate_import_data(data, "customer")
        assert any("重复" in e for e in result["errors"])

    def test_import_opportunities_missing_required_field(self, import_export_service):
        data = [{"name": "项目A", "amount": 100000}]
        result = import_export_service.validate_import_data(data, "opportunity")
        assert len(result["errors"]) > 0

    def test_import_leads_missing_required_field(self, import_export_service):
        data = [{"name": "王五", "email": "test@example.com"}]
        result = import_export_service.validate_import_data(data, "lead")
        assert len(result["errors"]) > 0

    async def test_export_customers_with_filters(self, import_export_service):
        result = await import_export_service.export_customers({"status": "活跃"}, "csv")
        assert isinstance(result, bytes)

    async def test_export_customers_excel_format(self, import_export_service):
        result = await import_export_service.export_customers({}, "excel")
        assert isinstance(result, bytes)

    async def test_export_opportunities_excel_format(self, import_export_service):
        result = await import_export_service.export_opportunities({}, "excel")
        assert isinstance(result, bytes)

    def test_validate_import_data_with_invalid_amount(self, import_export_service):
        data = [{"name": "项目", "customer_id": 1, "amount": "not-a-number"}]
        result = import_export_service.validate_import_data(data, "opportunity")
        assert len(result["errors"]) > 0

    def test_is_valid_email_various_formats(self, import_export_service):
        assert import_export_service._is_valid_email("test@example.com") is True
        assert import_export_service._is_valid_email("user.name+tag@example.co.uk") is True
        assert import_export_service._is_valid_email("invalid") is False
        assert import_export_service._is_valid_email("@example.com") is False
        assert import_export_service._is_valid_email("user@") is False

    def test_is_valid_phone_various_formats(self, import_export_service):
        assert import_export_service._is_valid_phone("13800138000") is True
        assert import_export_service._is_valid_phone("19912345678") is True
        assert import_export_service._is_valid_phone("1234567890") is False
        assert import_export_service._is_valid_phone("abc12345678") is False

    def test_is_valid_number(self, import_export_service):
        assert import_export_service._is_valid_number(100) is True
        assert import_export_service._is_valid_number(100.5) is True
        assert import_export_service._is_valid_number("100") is True
        assert import_export_service._is_valid_number("abc") is False

    def test_export_data_unsupported_format(self, import_export_service):
        with pytest.raises(ValueError, match="不支持"):
            import_export_service._export_data([], {}, "unsupported")

    def test_export_report_unsupported_format(self, import_export_service):
        with pytest.raises(ValueError, match="不支持"):
            import_export_service._export_data([], {}, "xml")

    def test_generate_pdf_report_minimal(self, import_export_service):
        report_data = {
            "summary": {"total": 100},
            "details": [],
        }
        result = import_export_service.generate_pdf_report(report_data, "最小报表")
        assert isinstance(result, bytes)

    async def test_import_customers_nested_json(self, import_export_service):
        data = {"customers": [
            {"name": "张三", "email": "zhangsan@example.com", "phone": "13800138000"},
        ]}
        json_content = json.dumps(data).encode('utf-8')
        result = await import_export_service.import_customers(json_content, "json")
        assert result["success_count"] == 1
