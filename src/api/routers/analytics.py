"""Analytics router — /api/v1/analytics/*

Wires the five aggregated-report methods on AnalyticsService to FastAPI GET
endpoints. Services raise AppException on errors (caught by global handler in
main.py). Router wraps successful results in {"success": True, "data": ..., "message": ...}.
"""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.analytics_service import AnalyticsService

analytics_router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _chart_response(data: dict) -> dict:
    return {"success": True, "data": data, "message": "查询成功"}


# ---------------------------------------------------------------------------
# GET /revenue
# ---------------------------------------------------------------------------


@analytics_router.get("/revenue")
async def get_sales_revenue(
    start_date: str = Query(..., description="Start date (ISO format, e.g. 2025-01-01)"),
    end_date: str = Query(..., description="End date (ISO format, e.g. 2025-01-31)"),
    group_by: Literal["day", "week", "month"] = Query(default="day", description="Grouping: day | week | month"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    data = await svc.get_sales_revenue_report(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        tenant_id=ctx.tenant_id or 0,
    )
    return _chart_response(data)


# ---------------------------------------------------------------------------
# GET /sales-conversion
# ---------------------------------------------------------------------------


@analytics_router.get("/sales-conversion")
async def get_sales_conversion(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    data = await svc.get_sales_conversion_report(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id or 0,
    )
    return _chart_response(data)


# ---------------------------------------------------------------------------
# GET /customer-growth
# ---------------------------------------------------------------------------


@analytics_router.get("/customer-growth")
async def get_customer_growth(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    data = await svc.get_customer_growth_report(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id or 0,
    )
    return _chart_response(data)


# ---------------------------------------------------------------------------
# GET /pipeline-forecast
# ---------------------------------------------------------------------------


@analytics_router.get("/pipeline-forecast")
async def get_pipeline_forecast(
    pipeline_id: int | None = Query(None, description="Pipeline ID (optional)"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    data = await svc.get_pipeline_forecast(
        pipeline_id=pipeline_id,
        tenant_id=ctx.tenant_id or 0,
    )
    return _chart_response(data)


# ---------------------------------------------------------------------------
# GET /team-performance
# ---------------------------------------------------------------------------


@analytics_router.get("/team-performance")
async def get_team_performance(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    data = await svc.get_team_performance(
        start_date=start_date,
        end_date=end_date,
        tenant_id=ctx.tenant_id or 0,
    )
    return _chart_response(data)


# ---------------------------------------------------------------------------
# GET /chart-data
# ---------------------------------------------------------------------------


@analytics_router.get("/chart-data")
async def get_chart_data(
    chart_type: str = Query(..., description="Chart type (e.g. line, bar, pie)"),
    data: str = Query(..., description="Comma-separated numbers or JSON array"),
    labels: str = Query(..., description="Comma-separated labels or JSON array"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    try:
        parsed_data: list = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        parsed_data = [float(x.strip()) for x in data.split(",") if x.strip()]

    try:
        parsed_labels: list[str] = json.loads(labels)
    except (json.JSONDecodeError, ValueError):
        parsed_labels = [x.strip() for x in labels.split(",") if x.strip()]

    svc = AnalyticsService(session)
    result = svc.get_chart_data(
        chart_type=chart_type,
        data=parsed_data,
        labels=parsed_labels,
    )
    return _chart_response(result)
