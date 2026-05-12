"""Report service router — /api/v1/reports endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps service return values in success envelopes.
"""

import base64

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.report_service import ReportService

reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=50)
    config: dict = Field(default_factory=dict)
    date_range: dict = Field(default_factory=dict)


class ReportUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    type: str | None = Field(None, max_length=50)
    config: dict | None = Field(None)
    date_range: dict | None = Field(None)


class GeneratePdfRequest(BaseModel):
    report_type: str = Field(..., min_length=1, max_length=50)
    config: dict = Field(default_factory=dict)
    date_range: dict | None = Field(None)


class GenerateExcelRequest(BaseModel):
    report_type: str = Field(..., min_length=1, max_length=50)
    config: dict = Field(default_factory=dict)
    date_range: dict | None = Field(None)


class ExportCsvRequest(BaseModel):
    table: str = Field(..., min_length=1, max_length=50)
    filename: str = Field(..., min_length=1, max_length=255)
    date_range: dict | None = Field(None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@reports_router.post("")
async def create_report(
    data: ReportCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a saved report configuration."""
    svc = ReportService(session)
    result = await svc.create_report(
        tenant_id=ctx.tenant_id,
        name=data.name,
        report_type=data.type,
        config=data.config,
        date_range=data.date_range,
        created_by=ctx.user_id,
    )
    return {"success": True, "data": result, "message": "报表创建成功"}


@reports_router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_type: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List saved report configurations."""
    svc = ReportService(session)
    result = await svc.list_reports(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        report_type=report_type,
    )
    return {"success": True, "data": result}


@reports_router.get("/{report_id}")
async def get_report(
    report_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a report config by ID."""
    svc = ReportService(session)
    result = await svc.get_report(report_id=report_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}


@reports_router.put("/{report_id}")
async def update_report(
    report_id: int,
    data: ReportUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update a report config."""
    svc = ReportService(session)
    kwargs = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    result = await svc.update_report(report_id=report_id, tenant_id=ctx.tenant_id, **kwargs)
    return {"success": True, "data": result, "message": "报表更新成功"}


@reports_router.delete("/{report_id}")
async def delete_report(
    report_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a report config."""
    svc = ReportService(session)
    result = await svc.delete_report(report_id=report_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "报表删除成功"}


@reports_router.post("/pdf")
async def generate_pdf(
    req: GeneratePdfRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Generate a PDF report. Returns binary PDF content."""
    svc = ReportService(session)
    data = await svc.generate_pdf_report(
        tenant_id=ctx.tenant_id,
        report_type=req.report_type,
        config=req.config,
        date_range=req.date_range,
    )
    content = base64.b64decode(data["content_base64"])
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{data["filename"]}"',
            "Content-Length": str(data["size_bytes"]),
        },
    )


@reports_router.post("/excel")
async def generate_excel(
    req: GenerateExcelRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Generate an Excel report. Returns binary XLSX content."""
    svc = ReportService(session)
    data = await svc.generate_excel_report(
        tenant_id=ctx.tenant_id,
        report_type=req.report_type,
        config=req.config,
        date_range=req.date_range,
    )
    content = base64.b64decode(data["content_base64"])
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{data["filename"]}"',
            "Content-Length": str(data["size_bytes"]),
        },
    )


@reports_router.post("/csv")
async def export_csv(
    req: ExportCsvRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Export a table to CSV. Returns binary CSV content."""
    svc = ReportService(session)
    data = await svc.export_to_csv(
        tenant_id=ctx.tenant_id,
        table=req.table,
        filename=req.filename,
        date_range=req.date_range,
    )
    content = base64.b64decode(data["content_base64"])
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{data["filename"]}"',
            "Content-Length": str(data["size_bytes"]),
        },
    )
