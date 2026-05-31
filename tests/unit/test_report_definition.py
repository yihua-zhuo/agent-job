"""
Unit tests for ReportDefinitionModel ORM model.
"""
from datetime import UTC, datetime

from db.models.report import ReportDefinitionModel


class TestReportDefinitionModel:
    """Tests for ReportDefinitionModel."""

    def test_tablename(self):
        """Test __tablename__ is set correctly."""
        assert ReportDefinitionModel.__tablename__ == "report_definitions"

    def test_create_with_required_fields(self):
        """Test creating a report definition with required fields."""
        report = ReportDefinitionModel(
            tenant_id=1,
            name="Q1 Sales Report",
            report_type="sales",
            config={"period": "Q1", "filters": []},
            owner_tenant_id=1,
            created_by=42,
        )

        assert report.tenant_id == 1
        assert report.name == "Q1 Sales Report"
        assert report.report_type == "sales"
        assert report.config == {"period": "Q1", "filters": []}
        assert report.owner_tenant_id == 1
        assert report.created_by == 42

    def test_field_defaults(self):
        """Test that optional fields have correct defaults.

        Note: SQLAlchemy's mapped_column(default=...) is a server-side default applied by the DB
        on INSERT. Python instances without explicit values have None for these fields until a
        flush/insert populates them from the DB default.
        """
        report = ReportDefinitionModel(
            tenant_id=1,
            name="Default Test",
            report_type="marketing",
            config={},
            owner_tenant_id=1,
            created_by=0,
        )

        # is_favorite defaults to False after DB insert; before insert it is None in Python
        assert report.is_favorite is None
        # created_at and updated_at are None before flush; DB sets them on insert
        assert report.created_at is None
        assert report.updated_at is None

    def test_to_dict_output(self):
        """Test to_dict returns all expected fields."""
        report = ReportDefinitionModel(
            id=5,
            tenant_id=10,
            name="Revenue Report",
            report_type="finance",
            config={"granularity": "daily"},
            owner_tenant_id=10,
            created_by=7,
            is_favorite=True,
        )
        # Set explicit datetimes for predictable output
        report.created_at = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        report.updated_at = datetime(2026, 2, 20, 14, 0, 0, tzinfo=UTC)

        result = report.to_dict()

        assert result["id"] == 5
        assert result["tenant_id"] == 10
        assert result["name"] == "Revenue Report"
        assert result["report_type"] == "finance"
        assert result["config"] == {"granularity": "daily"}
        assert result["owner_tenant_id"] == 10
        assert result["created_by"] == 7
        assert result["is_favorite"] is True
        assert result["created_at"] == "2026-01-15T10:30:00+00:00"
        assert result["updated_at"] == "2026-02-20T14:00:00+00:00"

    def test_to_dict_config_fallback(self):
        """Test to_dict returns empty dict when config is None."""
        report = ReportDefinitionModel(
            tenant_id=1,
            name="Test",
            report_type="sales",
            config=None,
            owner_tenant_id=1,
            created_by=0,
        )

        result = report.to_dict()
        assert result["config"] == {}

    def test_to_dict_datetimes_as_iso(self):
        """Test datetime fields are serialized as ISO strings."""
        report = ReportDefinitionModel(
            id=1,
            tenant_id=1,
            name="Test Report",
            report_type="sales",
            config={},
            owner_tenant_id=1,
            created_by=0,
        )
        report.created_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        report.updated_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        result = report.to_dict()
        assert result["created_at"].startswith("2026-03-01")
        assert result["updated_at"].startswith("2026-03-01")

    def test_to_dict_bools_ints_as_is(self):
        """Test bool and int fields are returned as-is."""
        report = ReportDefinitionModel(
            id=99,
            tenant_id=5,
            name="Test",
            report_type="marketing",
            config={},
            owner_tenant_id=3,
            created_by=12,
            is_favorite=False,
        )
        report.created_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        report.updated_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        result = report.to_dict()
        assert result["id"] == 99
        assert result["tenant_id"] == 5
        assert result["owner_tenant_id"] == 3
        assert result["created_by"] == 12
        assert result["is_favorite"] is False
