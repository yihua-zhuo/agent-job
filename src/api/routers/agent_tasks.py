"""Agent tasks router — /agents/tasks endpoints.

Services raise AppException on errors (caught by global handler in main.py).
AgentTaskModel objects have .to_dict(); router calls it before returning.
"""

from datetime import date
from datetime import datetime as dt_cls

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.agent_task_service import AgentTaskService

agent_tasks_router = APIRouter(prefix="/agents/tasks", tags=["Agent Tasks"])


def _paginated(items, total, page, page_size):
    has_next = page < (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [t.to_dict() for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": has_next,
        },
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AgentTaskCreate(BaseModel):
    description: str = Field(..., min_length=1)


def _date_to_datetime(d: date, end_of_day: bool = False) -> dt_cls:
    if end_of_day:
        from datetime import time
        return dt_cls.combine(d, time.max)
    return dt_cls.combine(d, dt_cls.min.time())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@agent_tasks_router.post("", status_code=201)
async def create_agent_task(
    body: AgentTaskCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = AgentTaskService(session)
    task = await service.create_task(description=body.description, tenant_id=ctx.tenant_id)
    return {"success": True, "data": task.to_dict()}


@agent_tasks_router.get("")
async def list_agent_tasks(
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = AgentTaskService(session)
    dt_from = _date_to_datetime(date_from) if date_from is not None else None
    dt_to = _date_to_datetime(date_to, end_of_day=True) if date_to is not None else None
    items, total = await service.list_tasks(
        tenant_id=ctx.tenant_id,
        status=status,
        date_from=dt_from,
        date_to=dt_to,
        page=page,
        page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@agent_tasks_router.get("/{agent_task_id}")
async def get_agent_task(
    agent_task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = AgentTaskService(session)
    task = await service.get_task(task_id=agent_task_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": task.to_dict()}
