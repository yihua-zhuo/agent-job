"""Tasks router — /api/v1/tasks endpoints.

Services raise AppException on errors (caught by global handler in main.py).
TaskModel objects have .to_dict(); router calls it before returning.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.task_service import TaskService

tasks_router = APIRouter(prefix="/api/v1", tags=["tasks"])

UNASSIGNED = 0


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
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


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    status: str = Field(default="pending", pattern="^(pending|in_progress|completed|cancelled)$")
    due_date: str | None = Field(default=None)
    assigned_to: int = Field(default=UNASSIGNED, ge=0)


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = Field(None, pattern="^(low|normal|high|urgent)$")
    status: str | None = Field(None, pattern="^(pending|in_progress|completed|cancelled)$")
    due_date: str | None = None
    assigned_to: int | None = Field(None, ge=0)


def _parse_due_date(val: str | None) -> datetime | None:
    if val is None:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@tasks_router.post("/tasks", status_code=201)
async def create_task(
    body: TaskCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    task = await service.create_task(
        title=body.title,
        description=body.description,
        priority=body.priority,
        tenant_id=ctx.tenant_id,
        created_by=ctx.user_id,
        assigned_to=body.assigned_to or UNASSIGNED,
        due_date=_parse_due_date(body.due_date),
    )
    return {"success": True, "data": task.to_dict(), "message": "Task created"}


@tasks_router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    assigned_to: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    items, total = await service.list_tasks(
        page=page,
        page_size=page_size,
        status=status,
        assigned_to=assigned_to,
        tenant_id=ctx.tenant_id,
    )
    return _paginated(items, total, page, page_size)


@tasks_router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    task = await service.get_task(tenant_id=ctx.tenant_id, task_id=task_id)
    return {"success": True, "data": task.to_dict()}


@tasks_router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: TaskUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    update_data = body.model_dump(exclude_none=True)
    if "due_date" in update_data:
        update_data["due_date"] = _parse_due_date(update_data["due_date"])
    task = await service.update_task(tenant_id=ctx.tenant_id, task_id=task_id, **update_data)
    return {"success": True, "data": task.to_dict(), "message": "Task updated"}


@tasks_router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    task = await service.complete_task(tenant_id=ctx.tenant_id, task_id=task_id)
    return {"success": True, "data": task.to_dict(), "message": "Task completed"}


@tasks_router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    await service.delete_task(tenant_id=ctx.tenant_id, task_id=task_id)
    return {"success": True, "data": None, "message": "Task deleted"}
