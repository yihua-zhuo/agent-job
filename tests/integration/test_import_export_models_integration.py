"""Integration tests for ImportJobModel and ExportJobModel ORM models.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_import_export_models_integration.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from db.models.export_job import ExportJobModel
from db.models.import_job import ImportJobModel

pytestmark = pytest.mark.integration


class TestImportJobModelIntegration:
    """CRUD + to_dict round-trip for ImportJobModel."""

    async def test_insert_and_select(self, db_schema, tenant_id, async_session):
        job = ImportJobModel(
            tenant_id=tenant_id,
            entity_type="customer",
            file_path="/uploads/import_001.csv",
            status="pending",
            total_rows=100,
            processed_rows=0,
            error_rows=0,
        )
        async_session.add(job)
        await async_session.flush()

        result = await async_session.execute(
            select(ImportJobModel).where(ImportJobModel.id == job.id)
        )
        fetched = result.scalar_one()
        assert fetched.tenant_id == tenant_id
        assert fetched.entity_type == "customer"
        assert fetched.file_path == "/uploads/import_001.csv"
        assert fetched.status == "pending"
        assert fetched.total_rows == 100
        assert fetched.processed_rows == 0
        assert fetched.error_rows == 0

    async def test_to_dict_after_db_roundtrip(self, db_schema, tenant_id, async_session):
        now = datetime.now(UTC)
        job = ImportJobModel(
            tenant_id=tenant_id,
            entity_type="opportunity",
            file_path="/uploads/opportunities.csv",
            status="completed",
            total_rows=50,
            processed_rows=50,
            error_rows=0,
            created_at=now,
            updated_at=now,
        )
        async_session.add(job)
        await async_session.flush()

        result = await async_session.execute(
            select(ImportJobModel).where(ImportJobModel.id == job.id)
        )
        fetched = result.scalar_one()
        d = fetched.to_dict()

        assert d["tenant_id"] == tenant_id
        assert d["entity_type"] == "opportunity"
        assert d["file_path"] == "/uploads/opportunities.csv"
        assert d["status"] == "completed"
        assert d["total_rows"] == 50
        assert d["processed_rows"] == 50
        assert d["error_rows"] == 0
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    async def test_query_by_tenant_id(self, db_schema, tenant_id, async_session):
        for i in range(3):
            async_session.add(
                ImportJobModel(
                    tenant_id=tenant_id,
                    entity_type="customer",
                    file_path=f"/uploads/import_{i}.csv",
                )
            )
        # Different tenant should not be returned
        async_session.add(
            ImportJobModel(
                tenant_id=9999,
                entity_type="customer",
                file_path="/uploads/other_tenant.csv",
            )
        )
        await async_session.flush()

        result = await async_session.execute(
            select(ImportJobModel).where(ImportJobModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 3


class TestExportJobModelIntegration:
    """CRUD + to_dict round-trip for ExportJobModel."""

    async def test_insert_and_select(self, db_schema, tenant_id, async_session):
        job = ExportJobModel(
            tenant_id=tenant_id,
            entity_type="customer",
            fields={"columns": ["name", "email"]},
            filters={"status": "active"},
            file_path="/exports/customers_001.csv",
            status="pending",
        )
        async_session.add(job)
        await async_session.flush()

        result = await async_session.execute(
            select(ExportJobModel).where(ExportJobModel.id == job.id)
        )
        fetched = result.scalar_one()
        assert fetched.tenant_id == tenant_id
        assert fetched.entity_type == "customer"
        assert fetched.fields == {"columns": ["name", "email"]}
        assert fetched.filters == {"status": "active"}
        assert fetched.file_path == "/exports/customers_001.csv"
        assert fetched.status == "pending"
        assert fetched.expires_at is None

    async def test_to_dict_after_db_roundtrip(self, db_schema, tenant_id, async_session):
        now = datetime.now(UTC)
        job = ExportJobModel(
            tenant_id=tenant_id,
            entity_type="opportunity",
            fields={"columns": ["name", "amount"]},
            filters={},
            file_path="/exports/opportunities.csv",
            status="completed",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        async_session.add(job)
        await async_session.flush()

        result = await async_session.execute(
            select(ExportJobModel).where(ExportJobModel.id == job.id)
        )
        fetched = result.scalar_one()
        d = fetched.to_dict()

        assert d["tenant_id"] == tenant_id
        assert d["entity_type"] == "opportunity"
        assert d["fields"] == {"columns": ["name", "amount"]}
        assert d["filters"] == {}
        assert d["file_path"] == "/exports/opportunities.csv"
        assert d["status"] == "completed"
        assert d["expires_at"] is not None
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    async def test_query_by_tenant_id(self, db_schema, tenant_id, async_session):
        for i in range(2):
            async_session.add(
                ExportJobModel(
                    tenant_id=tenant_id,
                    entity_type="customer",
                    fields={},
                    filters={},
                    file_path=f"/exports/export_{i}.csv",
                )
            )
        async_session.add(
            ExportJobModel(
                tenant_id=9999,
                entity_type="customer",
                fields={},
                filters={},
                file_path="/exports/other_tenant.csv",
            )
        )
        await async_session.flush()

        result = await async_session.execute(
            select(ExportJobModel).where(ExportJobModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
