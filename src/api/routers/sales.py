"""Sales router — /api/v1/sales/pipelines, /api/v1/sales/opportunities, /api/v1/sales/forecast.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps successful results in {"success": True, "data": ..., "message": ...}.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.sales_service import SalesService

sales_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas (requirement 9 — Field constraints)
# ---------------------------------------------------------------------------


class OpportunityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="商机名称")
    customer_id: int = Field(..., ge=1, description="客户 ID")
    pipeline_id: int = Field(..., ge=1, description="管道 ID")
    stage: str = Field(..., min_length=1, max_length=50, description="阶段")
    amount: float = Field(..., ge=0, description="金额")
    owner_id: int = Field(..., ge=0, description="负责人 ID")
    close_date: str | None = Field(None, description="预计关闭日期 ISO 格式")
    notes: str | None = Field(None, max_length=2000, description="备注")


class OpportunityUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    customer_id: int | None = Field(None, ge=1)
    pipeline_id: int | None = Field(None, ge=1)
    stage: str | None = Field(None, min_length=1, max_length=50)
    amount: float | None = Field(None, ge=0)
    owner_id: int | None = Field(None, ge=0)
    close_date: str | None = None
    notes: str | None = Field(None, max_length=2000)


class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="管道名称")
    is_default: bool | None = Field(default=False, description="是否默认管道")
    stages: list[str] | None = Field(default=None, description="阶段列表")


class StageChange(BaseModel):
    stage: str = Field(..., min_length=1, max_length=50)


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------


@sales_router.post("/pipelines", status_code=201)
async def create_pipeline(
    body: PipelineCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.create_pipeline(ctx.tenant_id, body.model_dump())
    return {"success": True, "data": data, "message": "管道创建成功"}


@sales_router.get("/pipelines")
async def list_pipelines(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    items = await service.list_pipelines(ctx.tenant_id)
    return {"success": True, "data": {"items": items, "total": len(items)}}


@sales_router.get("/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_pipeline(ctx.tenant_id, pipeline_id)
    return {"success": True, "data": data}


@sales_router.get("/pipelines/{pipeline_id}/stats")
async def get_pipeline_stats(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_pipeline_stats(ctx.tenant_id, pipeline_id)
    return {"success": True, "data": data}


@sales_router.get("/pipelines/{pipeline_id}/funnel")
async def get_pipeline_funnel(
    pipeline_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_pipeline_funnel(ctx.tenant_id, pipeline_id)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# Opportunity endpoints
# ---------------------------------------------------------------------------


@sales_router.post("/opportunities", status_code=201)
async def create_opportunity(
    body: OpportunityCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = body.model_dump()
    data["expected_close_date"] = data.pop("close_date", None)
    result = await service.create_opportunity(ctx.tenant_id, data)
    return {"success": True, "data": result, "message": "商机创建成功"}


@sales_router.get("/opportunities")
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline_id: int | None = None,
    stage: str | None = None,
    owner_id: int | None = None,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    items = await service.list_opportunities(
        ctx.tenant_id,
        page=page,
        page_size=page_size,
        pipeline_id=pipeline_id,
        stage=stage,
        owner_id=owner_id,
    )
    # Service returns a list for list methods
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
            "page": page,
            "page_size": page_size,
        },
    }


@sales_router.get("/opportunities/{opp_id}")
async def get_opportunity(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_opportunity(ctx.tenant_id, opp_id)
    return {"success": True, "data": data}


@sales_router.put("/opportunities/{opp_id}")
async def update_opportunity(
    opp_id: int,
    body: OpportunityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = body.model_dump(exclude_none=True)
    if "close_date" in data:
        data["expected_close_date"] = data.pop("close_date")
    result = await service.update_opportunity(ctx.tenant_id, opp_id, data)
    return {"success": True, "data": result, "message": "商机更新成功"}


@sales_router.put("/opportunities/{opp_id}/stage")
async def change_stage(
    opp_id: int,
    body: StageChange,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.change_stage(ctx.tenant_id, opp_id, body.stage)
    return {"success": True, "data": data, "message": "阶段变更成功"}


@sales_router.get("/forecast")
async def get_forecast(
    owner_id: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_forecast(ctx.tenant_id, owner_id=owner_id)
    return {"success": True, "data": data}
