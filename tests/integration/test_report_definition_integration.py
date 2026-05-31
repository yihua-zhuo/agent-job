"""
Integration tests for ReportDefinitionModel.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_report_definition_integration.py -v
"""
from __future__ import annotations

import pytest

from db.models.report import ReportDefinitionModel

pytestmark = pytest.mark.integration


class TestReportDefinitionIntegration:
    """DB-level round-trip tests for ReportDefinitionModel via AsyncSession."""

    async def test_insert_and_retrieve(self, async_session, tenant_id: int):
        """Insert a row and query it back, verifying all columns."""
        report = ReportDefinitionModel(
            tenant_id=tenant_id,
            name="Q1 Revenue Report",
            report_type="sales",
            config={"period": "Q1", "filters": ["region=north"]},
            owner_tenant_id=tenant_id,
            created_by=42,
            is_favorite=True,
        )
        async_session.add(report)
        await async_session.flush()
        await async_session.refresh(report)

        assert report.id is not None
        assert report.tenant_id == tenant_id
        assert report.name == "Q1 Revenue Report"
        assert report.report_type == "sales"
        assert report.config == {"period": "Q1", "filters": ["region=north"]}
        assert report.owner_tenant_id == tenant_id
        assert report.created_by == 42
        assert report.is_favorite is True
        assert report.created_at is not None
        assert report.updated_at is not None

    async def test_insert_with_defaults(self, async_session, tenant_id: int):
        """Insert a row without optional fields and verify defaults."""
        report = ReportDefinitionModel(
            tenant_id=tenant_id,
            name="Minimal Report",
            report_type="marketing",
            config={},
            owner_tenant_id=tenant_id,
            created_by=0,
        )
        async_session.add(report)
        await async_session.flush()
        await async_session.refresh(report)

        assert report.is_favorite is False
        assert report.created_at is not None
        assert report.updated_at is not None

    async def test_to_dict_roundtrip(self, async_session, tenant_id: int):
        """Insert a row, call to_dict, and verify all serialised fields."""
        report = ReportDefinitionModel(
            tenant_id=tenant_id,
            name="Dict Roundtrip Test",
            report_type="finance",
            config={"granularity": "daily"},
            owner_tenant_id=tenant_id,
            created_by=7,
            is_favorite=False,
        )
        async_session.add(report)
        await async_session.flush()
        await async_session.refresh(report)

        result = report.to_dict()

        assert result["id"] == report.id
        assert result["tenant_id"] == tenant_id
        assert result["name"] == "Dict Roundtrip Test"
        assert result["report_type"] == "finance"
        assert result["config"] == {"granularity": "daily"}
        assert result["owner_tenant_id"] == tenant_id
        assert result["created_by"] == 7
        assert result["is_favorite"] is False
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)

    async def test_update_fields(self, async_session, tenant_id: int):
        """Update an existing row and verify changes persist."""
        report = ReportDefinitionModel(
            tenant_id=tenant_id,
            name="Update Test",
            report_type="sales",
            config={},
            owner_tenant_id=tenant_id,
            created_by=1,
            is_favorite=False,
        )
        async_session.add(report)
        await async_session.flush()

        report.name = "Updated Name"
        report.is_favorite = True
        await async_session.flush()
        await async_session.refresh(report)

        assert report.name == "Updated Name"
        assert report.is_favorite is True

    async def test_cross_tenant_insert(self, async_session, tenant_id: int, tenant_id_2: int):
        """Insert report owned by a different tenant, verify isolation."""
        report = ReportDefinitionModel(
            tenant_id=tenant_id_2,
            name="Tenant B Report",
            report_type="crm",
            config={"source": "import"},
            owner_tenant_id=tenant_id_2,
            created_by=99,
            is_favorite=True,
        )
        async_session.add(report)
        await async_session.flush()
        await async_session.refresh(report)

        assert report.tenant_id == tenant_id_2
        assert report.owner_tenant_id == tenant_id_2
        assert report.created_by == 99
