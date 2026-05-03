"""Report service router — /api/v1/reports endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from services.report_service import ReportService

reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.CREATED: 201,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
    }
    return m.get(status, 400)


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


class ReportData(BaseModel):
    id: int
    tenant_id: int
    name: str
    type: str
    config: dict
    date_range: dict
    created_by: int
    last_run_at: str | None
    created_at: str | None


class ReportResponse(BaseModel):
    success: bool
    data: ReportData | None = None
    message: str | None = None


class ReportListData(BaseModel):
    items: list[ReportData]
    total: int
    page: int
    page_size: int


class ReportListResponse(BaseModel):
    success: bool
    data: ReportListData | None = None
    message: str | None = None


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
):
    """Create a saved report configuration."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.create_report(
            tenant_id=ctx.tenant_id,
            name=data.name,
            report_type=data.type,
            config=data.config,
            date_range=data.date_range,
            created_by=ctx.user_id,
        )
        return result.to_dict(status_code=_http_status(result.status))


@reports_router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_type: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
):
    """List saved report configurations."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.list_reports(
            tenant_id=ctx.tenant_id,
            page=page,
            page_size=page_size,
            report_type=report_type,
        )
        return result.to_dict()


@reports_router.get("/{report_id}")
async def get_report(
    report_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    """Get a report config by ID."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.get_report(report_id=report_id, tenant_id=ctx.tenant_id)
        return result.to_dict(status_code=_http_status(result.status))


@reports_router.put("/{report_id}")
async def update_report(
    report_id: int,
    data: ReportUpdate,
    ctx: AuthContext = Depends(require_auth),
):
    """Update a report config."""
    async with get_db() as session:
        svc = ReportService(session)
        kwargs = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        result = await svc.update_report(report_id=report_id, tenant_id=ctx.tenant_id, **kwargs)
        return result.to_dict(status_code=_http_status(result.status))


@reports_router.delete("/{report_id}")
async def delete_report(
    report_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    """Delete a report config."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.delete_report(report_id=report_id, tenant_id=ctx.tenant_id)
        return result.to_dict(status_code=_http_status(result.status))


@reports_router.post("/pdf")
async def generate_pdf(
    req: GeneratePdfRequest,
    ctx: AuthContext = Depends(require_auth),
):
    """Generate a PDF report. Returns binary PDF content."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.generate_pdf_report(
            tenant_id=ctx.tenant_id,
            report_type=req.report_type,
            config=req.config,
            date_range=req.date_range,
        )
        if result.status != ResponseStatus.SUCCESS:
            return result.to_dict(status_code=_http_status(result.status))
        data = result.data
        import binascii
        content = binascii.unhexlify(data["content_base64"])
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
):
    """Generate an Excel report. Returns binary XLSX content."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.generate_excel_report(
            tenant_id=ctx.tenant_id,
            report_type=req.report_type,
            config=req.config,
            date_range=req.date_range,
        )
        if result.status != ResponseStatus.SUCCESS:
            return result.to_dict(status_code=_http_status(result.status))
        data = result.data
        import binascii
        content = binascii.unhexlify(data["content_base64"])
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
):
    """Export a table to CSV. Returns binary CSV content."""
    async with get_db() as session:
        svc = ReportService(session)
        result = await svc.export_to_csv(
            tenant_id=ctx.tenant_id,
            table=req.table,
            filename=req.filename,
            date_range=req.date_range,
        )
        if result.status != ResponseStatus.SUCCESS:
            return result.to_dict(status_code=_http_status(result.status))
        data = result.data
        import binascii
        content = binascii.unhexlify(data["content_base64"])
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{data["filename"]}"',
                "Content-Length": str(data["size_bytes"]),
            },
        )
