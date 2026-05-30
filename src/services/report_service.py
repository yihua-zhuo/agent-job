"""Report service — DB-backed schedule storage + file generation."""

import base64
import csv
import io
import os
import tempfile
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.analytics import ReportModel
from db.models.report_schedule import ReportScheduleModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class ReportService:
    """报表生成服务 — schedules backed by PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _safe_export_filename(filename: str) -> str:
        candidate = os.path.basename(filename or "")
        if not candidate or candidate in {".", ".."} or os.path.isabs(filename) or candidate != filename:
            candidate = f"export-{uuid.uuid4().hex}.csv"
        return candidate

    async def generate_pdf_report(
        self,
        report_data: dict | None = None,
        title: str | None = None,
        tenant_id: int = 0,
        report_type: str | None = None,
        config: dict | None = None,
        date_range: dict | None = None,
    ) -> dict:
        """生成PDF报表 — sync, no DB needed."""
        report_data = report_data or {"config": config or {}, "date_range": date_range or {}}
        title = title or f"{report_type or 'report'} report"
        content = (
            "%PDF-1.4\n"
            f"1 0 obj << /Type /Catalog >> endobj\n% {title}\n"
            "%%EOF\n"
        ).encode()
        filename = f"{report_type or 'report'}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        return {
            "status": "generated",
            "title": title,
            "format": "pdf",
            "generated_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(content).decode("ascii"),
            "filename": filename,
            "size_bytes": len(content),
            "data_summary": {
                "labels_count": len(report_data.get("labels", [])),
                "datasets_count": len(report_data.get("datasets", [])),
            },
        }

    async def generate_excel_report(
        self,
        report_data: dict | None = None,
        title: str | None = None,
        tenant_id: int = 0,
        report_type: str | None = None,
        config: dict | None = None,
        date_range: dict | None = None,
    ) -> dict:
        """生成Excel报表 — sync, no DB needed."""
        report_data = report_data or {"config": config or {}, "date_range": date_range or {}}
        title = title or f"{report_type or 'report'} report"
        content = (
            "PK\x03\x04"
            f"Generated Excel placeholder for {title}\n"
        ).encode()
        filename = f"{report_type or 'report'}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.xlsx"
        return {
            "status": "generated",
            "title": title,
            "format": "excel",
            "generated_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(content).decode("ascii"),
            "filename": filename,
            "size_bytes": len(content),
            "data_summary": {
                "labels_count": len(report_data.get("labels", [])),
                "datasets_count": len(report_data.get("datasets", [])),
            },
        }

    async def export_to_csv(
        self,
        data: list[dict] | None = None,
        filename: str = "export.csv",
        tenant_id: int = 0,
        table: str | None = None,
        date_range: dict | None = None,
    ) -> dict:
        """导出CSV — writes to temp dir."""
        filename = self._safe_export_filename(filename)
        if data is None:
            data = [{"table": table or "unknown", "date_range": date_range or {}}]
        if not data:
            raise ValidationException("No data to export")

        headers = list(data[0].keys()) if isinstance(data[0], dict) else []
        rows = []
        for row in data:
            if isinstance(row, dict):
                rows.append([str(row.get(h, "")) for h in headers])
            else:
                rows.append([str(v) for v in row])

        output = io.StringIO()
        writer = csv.writer(output)
        if headers:
            writer.writerow(headers)
        writer.writerows(rows)
        content = output.getvalue().encode("utf-8")

        temp_dir = os.path.abspath(tempfile.gettempdir())
        filepath = os.path.abspath(os.path.join(temp_dir, filename))
        if os.path.commonpath([temp_dir, filepath]) != temp_dir:
            raise ValidationException("Invalid export filename")
        with open(filepath, "wb") as f:
            f.write(content)

        return {
            "status": "success",
            "filename": filename,
            "filepath": filepath,
            "rows_exported": len(rows),
            "generated_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(content).decode("ascii"),
            "size_bytes": len(content),
        }

    async def schedule_report(
        self,
        report_id: int,
        schedule: dict,
        tenant_id: int = 0,
    ) -> ReportScheduleModel:
        """定时生成报表 — upserts the schedule row for (tenant_id, report_id)."""
        result = await self.session.execute(
            select(ReportScheduleModel).where(
                and_(
                    ReportScheduleModel.tenant_id == tenant_id,
                    ReportScheduleModel.report_id == report_id,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.schedule = schedule
            existing.active = True
            existing.updated_at = datetime.now(UTC)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        entry = ReportScheduleModel(
            tenant_id=tenant_id,
            report_id=report_id,
            schedule=schedule,
            active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def list_reports(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReportModel], int]:
        """Return paginated reports for a tenant with total count."""
        offset = (max(1, page) - 1) * page_size

        count_result = await self.session.execute(
            select(func.count(ReportModel.id)).where(
                ReportModel.tenant_id == tenant_id
            )
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(ReportModel)
            .where(ReportModel.tenant_id == tenant_id)
            .order_by(ReportModel.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        reports = list(result.scalars().all())
        return reports, total

    async def get_report(self, report_id: int, tenant_id: int) -> ReportModel:
        """Fetch a single report, enforcing tenant isolation."""
        result = await self.session.execute(
            select(ReportModel).where(
                and_(
                    ReportModel.id == report_id,
                    ReportModel.tenant_id == tenant_id,
                )
            )
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise NotFoundException("Report")
        return report

    async def create_report(
        self,
        tenant_id: int,
        data: dict[str, Any],
    ) -> ReportModel:
        """Insert a new report row for the given tenant."""
        now = datetime.now(UTC)
        report = ReportModel(
            tenant_id=tenant_id,
            name=data.get("name", "Unnamed Report"),
            type=data.get("type", "custom"),
            config=data.get("config", {}),
            date_range=data.get("date_range", {}),
            created_by=data.get("created_by", 0),
            last_run_at=None,
            created_at=now,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def update_report(
        self,
        report_id: int,
        tenant_id: int,
        data: dict[str, Any],
    ) -> ReportModel:
        """Partial update of a report; raises NotFoundException if missing or wrong tenant."""
        result = await self.session.execute(
            select(ReportModel).where(
                and_(
                    ReportModel.id == report_id,
                    ReportModel.tenant_id == tenant_id,
                )
            )
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise NotFoundException("Report")

        for field in ("name", "type", "config", "date_range", "last_run_at"):
            if field in data:
                setattr(report, field, data[field])

        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def delete_report(self, report_id: int, tenant_id: int) -> None:
        """Hard-delete a report row; raises NotFoundException if missing or wrong tenant."""
        result = await self.session.execute(
            select(ReportModel.id).where(
                and_(
                    ReportModel.id == report_id,
                    ReportModel.tenant_id == tenant_id,
                )
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("Report")

        await self.session.execute(
            delete(ReportModel).where(
                and_(
                    ReportModel.id == report_id,
                    ReportModel.tenant_id == tenant_id,
                )
            )
        )
        await self.session.flush()
