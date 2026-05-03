"""Activities router — /api/v1/activities endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from db.connection import get_db
from internal.middleware.fastapi_auth import require_auth, AuthContext
from services.activity_service import ActivityService
from models.response import ResponseStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope

activities_router = APIRouter(prefix='/api/v1/activities', tags=['activities'])


def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ActivityCreate(BaseModel):
    customer_id: int = Field(..., ge=1)
    activity_type: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1, max_length=5000)
    created_by: int = Field(..., ge=1)
    opportunity_id: Optional[int] = Field(None, ge=1)


class ActivityUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    activity_type: Optional[str] = Field(None, min_length=1, max_length=50)
    opportunity_id: Optional[int] = Field(None, ge=1)


class ActivitySearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)


class ActivityData(BaseModel):
    id: int
    tenant_id: int
    customer_id: int
    opportunity_id: Optional[int] = None
    type: str
    content: str
    created_by: int
    created_at: Optional[str] = None


class ActivityResponse(SuccessEnvelope):
    data: Optional[ActivityData] = None


class ActivityListData(BaseModel):
    items: List[ActivityData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class ActivityListResponse(SuccessEnvelope):
    data: ActivityListData


class ActivitySearchData(BaseModel):
    items: List[dict]


class ActivitySearchResponse(SuccessEnvelope):
    data: ActivitySearchData


class ActivitySummaryData(BaseModel):
    total: int
    by_type: dict
    recent_activities: List[dict]


class ActivitySummaryResponse(SuccessEnvelope):
    data: ActivitySummaryData


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _activity_to_data(activity) -> ActivityData:
    type_val = activity.type.value if hasattr(activity.type, "value") else str(activity.type)
    return ActivityData(
        id=activity.id,
        tenant_id=activity.tenant_id,
        customer_id=activity.customer_id,
        opportunity_id=activity.opportunity_id,
        type=type_val,
        content=activity.content,
        created_by=activity.created_by,
        created_at=activity.created_at.isoformat() if activity.created_at else None,
    )


@activities_router.post(
    '',
    status_code=201,
    response_model=ActivityResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_activity(
    body: ActivityCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.create_activity(
        customer_id=body.customer_id,
        activity_type=body.activity_type,
        content=body.content,
        created_by=body.created_by,
        tenant_id=ctx.tenant_id or 0,
        opportunity_id=body.opportunity_id,
    )
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return ActivityResponse(message=resp.message, data=_activity_to_data(resp.data))



@activities_router.get(
    '/summary',
    response_model=ActivitySummaryResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_activity_summary(
    customer_id: int = Query(..., ge=1),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    from datetime import datetime
    service = ActivityService(session)
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid start_date format")
    try:
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid end_date format")
    resp = await service.get_activity_summary(
        customer_id=customer_id,
        start_date=start,
        end_date=end,
        tenant_id=ctx.tenant_id or 0,
    )
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    return ActivitySummaryResponse(message=resp.message, data=resp.data)

@activities_router.get(
    '/{activity_id}',
    response_model=ActivityResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def get_activity(
    activity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.get_activity(activity_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return ActivityResponse(message=resp.message, data=_activity_to_data(resp.data))


@activities_router.put(
    '/{activity_id}',
    response_model=ActivityResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def update_activity(
    activity_id: int,
    body: ActivityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    update_data = body.model_dump(exclude_none=True)
    resp = await service.update_activity(activity_id, tenant_id=ctx.tenant_id or 0, **update_data)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return ActivityResponse(message=resp.message, data=_activity_to_data(resp.data))


@activities_router.delete(
    '/{activity_id}',
    response_model=ActivityResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def delete_activity(
    activity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.delete_activity(activity_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return ActivityResponse(message=resp.message, data=resp.data)


@activities_router.get(
    '',
    response_model=ActivityListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[int] = Query(None, ge=1),
    activity_type: Optional[str] = Query(None, max_length=50),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.list_activities(
        page=page, page_size=page_size,
        customer_id=customer_id, activity_type=activity_type,
        tenant_id=ctx.tenant_id or 0,
    )
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    items = [_activity_to_data(a) for a in resp.data.items]
    total_pages = (resp.data.total + resp.data.page_size - 1) // resp.data.page_size if resp.data.page_size > 0 else 0
    return ActivityListResponse(
        message=resp.message,
        data=ActivityListData(
            items=items,
            total=resp.data.total,
            page=resp.data.page,
            page_size=resp.data.page_size,
            total_pages=total_pages,
            has_next=resp.data.page < total_pages,
            has_prev=resp.data.page > 1,
        ),
    )


@activities_router.get(
    '/customer/{customer_id}',
    response_model=ActivityListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_customer_activities(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.get_customer_activities(customer_id, tenant_id=ctx.tenant_id or 0)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    items = [a.to_dict() if hasattr(a, "to_dict") else a for a in resp.data]
    # Convert dicts to ActivityData
    activity_items = []
    for item in items:
        if isinstance(item, dict):
            activity_items.append(ActivityData(
                id=item.get("id", 0),
                tenant_id=item.get("tenant_id", 0),
                customer_id=item.get("customer_id", 0),
                opportunity_id=item.get("opportunity_id"),
                type=item.get("type", ""),
                content=item.get("content", ""),
                created_by=item.get("created_by", 0),
                created_at=item.get("created_at"),
            ))
    return ActivityListResponse(
        message=resp.message,
        data=ActivityListData(
            items=activity_items,
            total=len(activity_items),
            page=1,
            page_size=len(activity_items),
            total_pages=1,
            has_next=False,
            has_prev=False,
        ),
    )


@activities_router.get(
    '/opportunity/{opp_id}',
    response_model=ActivityListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_opportunity_activities(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.get_opportunity_activities(opp_id, tenant_id=ctx.tenant_id or 0)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    items = [a.to_dict() if hasattr(a, "to_dict") else a for a in resp.data]
    activity_items = []
    for item in items:
        if isinstance(item, dict):
            activity_items.append(ActivityData(
                id=item.get("id", 0),
                tenant_id=item.get("tenant_id", 0),
                customer_id=item.get("customer_id", 0),
                opportunity_id=item.get("opportunity_id"),
                type=item.get("type", ""),
                content=item.get("content", ""),
                created_by=item.get("created_by", 0),
                created_at=item.get("created_at"),
            ))
    return ActivityListResponse(
        message=resp.message,
        data=ActivityListData(
            items=activity_items,
            total=len(activity_items),
            page=1,
            page_size=len(activity_items),
            total_pages=1,
            has_next=False,
            has_prev=False,
        ),
    )


@activities_router.post(
    '/search',
    response_model=ActivitySearchResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def search_activities(
    body: ActivitySearchRequest,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = ActivityService(session)
    resp = await service.search_activities(body.keyword, tenant_id=ctx.tenant_id or 0)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    items = [a.to_dict() if hasattr(a, "to_dict") else a for a in resp.data]
    return ActivitySearchResponse(
        message=resp.message,
        data=ActivitySearchData(items=items),
    )

