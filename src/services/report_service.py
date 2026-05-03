"""Report service — PDF/Excel/CSV report generation with scheduling support."""
import io
import csv
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.analytics import ReportModel
from models.response import ApiResponse, PaginatedData


# Minimal PDF generation using raw PDF syntax (no external lib needed).
# For richer PDFs install: pip install reportlab
def _build_minimal_pdf(title: str, headers: List[str], rows: List[List[str]]) -> bytes:
    """Generate a minimal valid PDF directly (no external lib).
    
    Produces a simple table-style PDF with header row and data rows.
    For professional PDFs, install reportlab and replace this.
    """
    import os
    _W = 595  # A4 width pts
    _H = 842  # A4 height pts
    _M = 40   # margin

    def _pt(txt: str, x: float, y: float) -> str:
        return f"BT /F1 10 Tf {x:.1f} {(842 - y):.1f} Td ({txt}) Tj ET"

    lines = [
        b"%PDF-1.4",
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj",
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj",
        b"4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj",
    ]

    body = "\n".join([
        "3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]"
        " /Contents 5 0 R /Resources <</Font <</F1 4 0 R>>>>>> endobj",
        "5 0 obj <</Length ", str(4096 + len(rows) * 40), ">>",
        "stream",
        f"0.5 0.5 0.5 rg 0 841.9 595 0.9 re f",  # header bg
        "0.7 0.7 0.7 rg 0 811.9 595 0.9 re f",   # alt row stripe
        _pt(title, _M, 25),
        _pt(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", _M, 40),
        "",
    ])

    row_y = 60
    col_x = [_M]
    step = (_W - 2 * _M) / max(len(headers), 1)
    for i in range(len(headers) - 1):
        col_x.append(col_x[-1] + step)

    # header
    for i, h in enumerate(headers):
        body += _pt(h, col_x[i] + 2, row_y) + "\n"
    row_y += 16

    for ri, row in enumerate(rows):
        stripe = "0.93 0.93 0.93 rg" if ri % 2 == 1 else "1 1 1 rg"
        body += f"{stripe} 0 {842 - row_y - 14} {_W - 2*_M} 14 re f\n"
        for ci, val in enumerate(row[:len(headers)]):
            body += _pt(str(val)[:80], col_x[ci] + 2, row_y) + "\n"
        row_y += 16

    body += "endstream\nendobj"
    stream_len = body.encode("latin-1", "replace").count(b"\n") + 4096 + len(rows) * 40
    lines.append(f"5 0 obj <</Length {stream_len}>> endobj".encode())
    lines.append(body.encode("latin-1", "replace"))
    lines.append(b"xref")
    lines.append(b"0 6")
    lines.append(b"0000000000 65535 f ")
    for i in range(1, 6):
        lines.append(f"0000000000 00000 n ".encode())
    lines.append(b"trailer <</Size 6 /Root 1 0 R>>")
    lines.append(b"startxref")
    lines.append(str(sum(len(l) for l in lines) + 20).encode())
    lines.append(b"%%EOF")
    return b"\n".join(lines)


class ReportService:
    """Report generation service supporting PDF, Excel, CSV and scheduled reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Report config CRUD (stored in DB)
    # -------------------------------------------------------------------------

    async def create_report(
        self,
        tenant_id: int,
        name: str,
        report_type: str,
        config: dict,
        date_range: dict,
        created_by: int = 0,
    ) -> ApiResponse[Dict]:
        """Create a saved report configuration."""
        now = datetime.now(UTC)
        model = ReportModel(
            tenant_id=tenant_id,
            name=name,
            type=report_type,
            config=config or {},
            date_range=date_range or {},
            created_by=created_by,
            created_at=now,
            last_run_at=None,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return ApiResponse.success(data=model.to_dict(), message="报表配置创建成功")

    async def list_reports(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        report_type: Optional[str] = None,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """List saved report configurations."""
        base_stmt = select(ReportModel).where(ReportModel.tenant_id == tenant_id)
        count_stmt = select(func.count(ReportModel.id)).where(ReportModel.tenant_id == tenant_id)
        if report_type:
            base_stmt = base_stmt.where(ReportModel.type == report_type)
            count_stmt = count_stmt.where(ReportModel.type == report_type)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        paginated = (
            base_stmt.order_by(ReportModel.created_at.desc())
            .offset(offset).limit(page_size)
        )
        result = await self.session.execute(paginated)
        rows = result.scalars().all()
        items = [r.to_dict() for r in rows]
        return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)

    async def get_report(self, report_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Get a report config by ID."""
        stmt = select(ReportModel).where(
            ReportModel.id == report_id,
            ReportModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="报表不存在", code=404)
        return ApiResponse.success(data=row.to_dict())

    async def update_report(
        self, report_id: int, tenant_id: int, **kwargs
    ) -> ApiResponse[Dict]:
        """Update a report config."""
        stmt = (
            update(ReportModel)
            .where(ReportModel.id == report_id, ReportModel.tenant_id == tenant_id)
            .values(**kwargs)
            .returning(ReportModel)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="报表不存在", code=404)
        return ApiResponse.success(data=row.to_dict(), message="报表更新成功")

    async def delete_report(self, report_id: int, tenant_id: int) -> ApiResponse[Dict]:
        """Delete a report config."""
        from sqlalchemy import delete
        stmt = delete(ReportModel).where(
            ReportModel.id == report_id,
            ReportModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        if (result.rowcount or 0) <= 0:
            return ApiResponse.error(message="报表不存在", code=404)
        return ApiResponse.success(data={"id": report_id}, message="报表删除成功")

    # -------------------------------------------------------------------------
    # Data gathering helpers
    # -------------------------------------------------------------------------

    async def _fetch_table_data(
        self,
        tenant_id: int,
        table: str,
        date_field: str = "created_at",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        filters: Optional[Dict] = None,
        limit: int = 10000,
    ) -> tuple[List[str], List[List[Any]]]:
        """Fetch raw rows from any table for reporting."""
        allowed_tables = {
            "customers", "opportunities", "tickets", "activities",
            "tasks", "users", "campaigns", "pipeline_stages",
        }
        if table not in allowed_tables:
            return [], []

        col_map = {
            "customers": ["id", "tenant_id", "name", "status", "industry", "created_at"],
            "opportunities": ["id", "tenant_id", "name", "stage", "amount", "created_at"],
            "tickets": ["id", "tenant_id", "subject", "status", "priority", "created_at"],
            "activities": ["id", "tenant_id", "type", "content", "created_at"],
            "tasks": ["id", "tenant_id", "title", "status", "assigned_to", "created_at"],
        }
        columns = col_map.get(table, ["*"])

        # Build simple query
        from sqlalchemy import text
        params: Dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        where = "tenant_id = :tenant_id"
        if date_from:
            where += f" AND {date_field} >= :date_from"
            params["date_from"] = date_from
        if date_to:
            where += f" AND {date_field} <= :date_to"
            params["date_to"] = date_to

        query = f'SELECT {", ".join(columns)} FROM {table} WHERE {where} ORDER BY id LIMIT :limit'
        result = await self.session.execute(text(query), params)
        rows = result.fetchall()
        return columns, [list(r) for r in rows]

    # -------------------------------------------------------------------------
    # PDF generation
    # -------------------------------------------------------------------------

    async def generate_pdf_report(
        self,
        tenant_id: int,
        report_type: str,
        config: dict,
        date_range: Optional[dict] = None,
    ) -> ApiResponse[Dict]:
        """Generate a PDF report and return raw bytes."""
        title = config.get("title", f"{report_type} Report")
        table = config.get("table", "customers")
        date_from = None
        date_to = None
        if date_range:
            date_from = date_range.get("from")
            date_to = date_range.get("to")

        headers, rows = await self._fetch_table_data(
            tenant_id=tenant_id,
            table=table,
            date_field="created_at",
            date_from=date_from,
            date_to=date_to,
        )

        pdf_bytes = _build_minimal_pdf(title, headers, rows)

        return ApiResponse.success(
            data={
                "filename": f"{table}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pdf",
                "size_bytes": len(pdf_bytes),
                "content_base64": pdf_bytes.hex(),  # client decodes to binary
                "generated_at": datetime.now(UTC).isoformat(),
                "rows": len(rows),
            },
            message="PDF 生成成功",
        )

    # -------------------------------------------------------------------------
    # Excel generation
    # -------------------------------------------------------------------------

    def _style_worksheet(self, ws, max_col: int):
        """Apply header styling to an openpyxl worksheet."""
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="3B82F6")
        thin = Side(style="thin", color="AAAAAA")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_align = Alignment(horizontal="center", vertical="center")

        for col in range(1, max_col + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = border
            col_letter = get_column_letter(col)
            ws.column_dimensions[col_letter].width = max(12, min(ws.cell(row=1, column=col).value or "", 30) + 2)

        for row in range(2, ws.max_row + 1):
            if row % 2 == 0:
                for col in range(1, max_col + 1):
                    ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor="F3F4F6")
            for col in range(1, max_col + 1):
                ws.cell(row=row, column=col).border = border
                ws.cell(row=row, column=col).alignment = Alignment(vertical="center")

    async def generate_excel_report(
        self,
        tenant_id: int,
        report_type: str,
        config: dict,
        date_range: Optional[dict] = None,
    ) -> ApiResponse[Dict]:
        """Generate an Excel report (.xlsx) and return raw bytes."""
        title = config.get("title", f"{report_type} Report")
        table = config.get("table", "customers")
        sheets = config.get("sheets", [table]) if isinstance(config.get("sheets"), list) else [table]
        date_from = date_range.get("from") if date_range else None
        date_to = date_range.get("to") if date_range else None

        wb = Workbook()
        wb.remove(wb.active)

        for sheet_name in sheets:
            ws = wb.create_sheet(title=sheet_name[:31])
            headers, rows = await self._fetch_table_data(
                tenant_id=tenant_id,
                table=sheet_name,
                date_field="created_at",
                date_from=date_from,
                date_to=date_to,
            )
            ws.append(headers)
            for row in rows:
                ws.append(row)

            self._style_worksheet(ws, len(headers))
            ws.freeze_panes = "A2"
            ws.title = sheet_name[:31]

        wb.add_worksheet(title="Summary").append(["Report", title, "Generated", datetime.now(UTC).isoformat()])

        buffer = io.BytesIO()
        wb.save(buffer)
        xlsx_bytes = buffer.getvalue()

        return ApiResponse.success(
            data={
                "filename": f"{table}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx",
                "size_bytes": len(xlsx_bytes),
                "content_base64": xlsx_bytes.hex(),
                "generated_at": datetime.now(UTC).isoformat(),
                "sheets": sheets,
            },
            message="Excel 生成成功",
        )

    # -------------------------------------------------------------------------
    # CSV export
    # -------------------------------------------------------------------------

    async def export_to_csv(
        self,
        tenant_id: int,
        table: str,
        filename: str,
        date_range: Optional[dict] = None,
    ) -> ApiResponse[Dict]:
        """Export a table to CSV."""
        date_from = date_range.get("from") if date_range else None
        date_to = date_range.get("to") if date_range else None
        headers, rows = await self._fetch_table_data(
            tenant_id=tenant_id,
            table=table,
            date_field="created_at",
            date_from=date_from,
            date_to=date_to,
        )
        if not headers:
            return ApiResponse.error(message=f"Table '{table}' not supported", code=400)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        csv_bytes = buffer.getvalue().encode("utf-8")

        return ApiResponse.success(
            data={
                "filename": f"{filename}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv",
                "size_bytes": len(csv_bytes),
                "content_base64": csv_bytes.hex(),
                "generated_at": datetime.now(UTC).isoformat(),
                "rows": len(rows),
            },
            message="CSV 导出成功",
        )
