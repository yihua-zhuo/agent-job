"""Activities router — /api/v1/activities endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router serializes ORM objects via .to_dict().
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.activity_service import ActivityService

activities_router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ActivityCreate(BaseModel):
    customer_id: int = Field(..., ge=1)
    activity_type: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1, max_length=5000)
    created_by: int = Field(..., ge=1)
    opportunity_id: int | None = Field(None, ge=1)


class ActivityUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=5000)
    activity_type: str | None = Field(None, min_length=1, max_length=50)
    opportunity_id: int | None = Field(None, ge=1)


class ActivitySearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@activities_router.post("", status_code=201)
async def create_activity(
    body: ActivityCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    activity = await service.create_activity(
        customer_id=body.customer_id,
        activity_type=body.activity_type,
        content=body.content,
        created_by=body.created_by,
        tenant_id=ctx.tenant_id,
        opportunity_id=body.opportunity_id,
    )
    return {"success": True, "data": activity.to_dict(), "message": "活动创建成功"}


@activities_router.get("/summary")
async def get_activity_summary(
    customer_id: int = Query(..., ge=1),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime

    try:
        start = datetime.fromisoformat(start_date) if start_date else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid start_date format")
    try:
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid end_date format")

    service = ActivityService(session)
    data = await service.get_activity_summary(
        customer_id=customer_id,
        start_date=start,
        end_date=end,
        tenant_id=ctx.tenant_id,
    )
    return {"success": True, "data": data}


@activities_router.get("/{activity_id}")
async def get_activity(
    activity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    activity = await service.get_activity(activity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": activity.to_dict()}


@activities_router.put("/{activity_id}")
async def update_activity(
    activity_id: int,
    body: ActivityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    update_data = body.model_dump(exclude_none=True)
    activity = await service.update_activity(activity_id, tenant_id=ctx.tenant_id, **update_data)
    return {"success": True, "data": activity.to_dict(), "message": "活动更新成功"}


@activities_router.delete("/{activity_id}")
async def delete_activity(
    activity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    await service.delete_activity(activity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": None, "message": "活动删除成功"}


@activities_router.get("")
async def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None, ge=1),
    activity_type: str | None = Query(None, max_length=50),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    items, total = await service.list_activities(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        activity_type=activity_type,
        tenant_id=ctx.tenant_id,
    )
    return _paginated(items, total, page, page_size)


@activities_router.get("/customer/{customer_id}")
async def get_customer_activities(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    activities = await service.get_customer_activities(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [a.to_dict() for a in activities]}


@activities_router.get("/opportunity/{opp_id}")
async def get_opportunity_activities(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    activities = await service.get_opportunity_activities(opp_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [a.to_dict() for a in activities]}


@activities_router.post("/search")
async def search_activities(
    body: ActivitySearchRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = ActivityService(session)
    activities = await service.search_activities(body.keyword, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [a.to_dict() for a in activities]}
