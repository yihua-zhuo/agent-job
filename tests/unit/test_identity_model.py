"""
Unit tests for identity ORM models (OrganizationModel, DepartmentModel).
"""
from datetime import datetime

from db.models.identity import DepartmentModel, OrganizationModel


class TestOrganizationModel:
    """Tests for OrganizationModel."""

    def test_default_status_is_active(self):
        """OrganizationModel status defaults to 'active' when not provided."""
        org = OrganizationModel(tenant_id=1, name="Test Org", status="active")
        assert org.status == "active"

    def test_explicit_field_values(self):
        """OrganizationModel accepts explicit values for all fields."""
        org = OrganizationModel(
            id=5,
            tenant_id=2,
            name="Acme Corp",
            status="inactive",
            description="A test organization",
        )
        assert org.id == 5
        assert org.tenant_id == 2
        assert org.name == "Acme Corp"
        assert org.status == "inactive"
        assert org.description == "A test organization"
        assert org.created_at is None  # server_default not applied without DB
        assert org.updated_at is None

    def test_description_is_nullable(self):
        """OrganizationModel description can be None."""
        org = OrganizationModel(tenant_id=1, name="No Desc Org", description=None)
        assert org.description is None

    def test_to_dict_includes_all_fields(self):
        """OrganizationModel.to_dict() returns all scalar fields."""
        now = datetime(2024, 1, 15, 10, 30, 0)
        org = OrganizationModel(
            id=3,
            tenant_id=7,
            name="Widgets Inc",
            status="active",
            description="Makes widgets",
            created_at=now,
            updated_at=now,
        )
        d = org.to_dict()
        assert d["id"] == 3
        assert d["tenant_id"] == 7
        assert d["name"] == "Widgets Inc"
        assert d["status"] == "active"
        assert d["description"] == "Makes widgets"
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_description_null(self):
        """OrganizationModel.to_dict() handles None description."""
        org = OrganizationModel(id=1, tenant_id=1, name="Null Desc")
        d = org.to_dict()
        assert d["description"] is None
        assert d["created_at"] is None
        assert d["updated_at"] is None


class TestDepartmentModel:
    """Tests for DepartmentModel."""

    def test_default_status_is_active(self):
        """DepartmentModel status defaults to 'active' when not provided."""
        dept = DepartmentModel(tenant_id=1, organization_id=1, name="Engineering", status="active")
        assert dept.status == "active"

    def test_explicit_field_values(self):
        """DepartmentModel accepts explicit values for all fields."""
        now = datetime(2024, 3, 1, 9, 0, 0)
        dept = DepartmentModel(
            id=10,
            tenant_id=3,
            organization_id=5,
            name="Sales",
            status="inactive",
            created_at=now,
            updated_at=now,
        )
        assert dept.id == 10
        assert dept.tenant_id == 3
        assert dept.organization_id == 5
        assert dept.name == "Sales"
        assert dept.status == "inactive"
        assert dept.created_at == now
        assert dept.updated_at == now

    def test_to_dict_includes_all_fields(self):
        """DepartmentModel.to_dict() returns all scalar fields."""
        now = datetime(2024, 3, 1, 9, 0, 0)
        dept = DepartmentModel(
            id=4,
            tenant_id=8,
            organization_id=2,
            name="HR Department",
            status="active",
            created_at=now,
            updated_at=now,
        )
        d = dept.to_dict()
        assert d["id"] == 4
        assert d["tenant_id"] == 8
        assert d["organization_id"] == 2
        assert d["name"] == "HR Department"
        assert d["status"] == "active"
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_to_dict_with_null_timestamps(self):
        """DepartmentModel.to_dict() handles None timestamps."""
        dept = DepartmentModel(id=1, tenant_id=1, organization_id=1, name="Minimal")
        d = dept.to_dict()
        assert d["id"] == 1
        assert d["created_at"] is None
        assert d["updated_at"] is None
