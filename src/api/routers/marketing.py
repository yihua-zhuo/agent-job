"""Marketing router — all /api/v1/marketing/campaigns endpoints.

Services raise AppException subclasses on errors (caught by global handler in main.py).
Router wraps successful returns in {"success": True, "data": ...} dicts.
"""
import math

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.marketing_service import MarketingService

marketing_router = APIRouter(prefix="/api/v1/marketing", tags=["marketing"])


def _paginated(items, total, page, page_size):
    total_pages = math.ceil(total / page_size) if page_size else 0
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
# Request schemas
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="活动名称")
    type: str = Field(..., description="活动类型: email, sms, push, auto, social, advertising")
    status: str = Field(default="draft", description="状态: draft, active, paused, completed, cancelled, scheduled")
    subject: str | None = Field(None, max_length=500, description="邮件主题")
    content: str | None = Field(None, description="活动内容")
    target_audience: str | None = Field(None, description="目标受众")
    start_date: str | None = Field(None, description="开始日期 (ISO 8601)")
    end_date: str | None = Field(None, description="结束日期 (ISO 8601)")
    budget: float | None = Field(None, ge=0, description="预算")


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    type: str | None = Field(None)
    status: str | None = Field(None)
    subject: str | None = Field(None, max_length=500)
    content: str | None = Field(None)
    target_audience: str | None = Field(None)
    start_date: str | None = Field(None)
    end_date: str | None = Field(None)
    budget: float | None = Field(None, ge=0)


class CampaignPaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: str | None = Field(None, description="按状态过滤")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@marketing_router.get("/campaigns")
async def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    items, total = await svc.list_campaigns(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return _paginated([item.to_dict() for item in items], total, page, page_size)


@marketing_router.post("/campaigns", status_code=201)
async def create_campaign(
    body: CampaignCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    campaign = await svc.create_campaign(
        name=body.name,
        campaign_type=body.type,
        content=body.content or "",
        created_by=ctx.user_id,
        tenant_id=ctx.tenant_id,
        subject=body.subject,
        target_audience=body.target_audience,
    )
    return {"success": True, "data": campaign.to_dict()}


@marketing_router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    campaign = await svc.get_campaign(campaign_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": campaign.to_dict()}


@marketing_router.put("/campaigns/{campaign_id}")
async def update_campaign_put(
    campaign_id: int,
    body: CampaignUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    # Build kwargs from non-None fields only
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    campaign = await svc.update_campaign(campaign_id, tenant_id=ctx.tenant_id, **kwargs)
    return {"success": True, "data": campaign.to_dict()}


@marketing_router.patch("/campaigns/{campaign_id}")
async def update_campaign_patch(
    campaign_id: int,
    body: CampaignUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    campaign = await svc.update_campaign(campaign_id, tenant_id=ctx.tenant_id, **kwargs)
    return {"success": True, "data": campaign.to_dict()}


@marketing_router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MarketingService(session)
    campaign = await svc.delete_campaign(campaign_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": campaign.to_dict()}
