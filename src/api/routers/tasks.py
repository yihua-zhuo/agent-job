"""Tasks router — /api/v1/tasks endpoints.

Services raise AppException on errors (caught by global handler in main.py).
TaskModel objects have .to_dict(); router calls it before returning.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.task_service import TaskService

tasks_router = APIRouter(prefix="/api/v1", tags=["tasks"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "success": True,
        "data": {
            "items": [t.to_dict() for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
        "message": "Task list retrieved",
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    assigned_to: int = Field(default=0, ge=0)
    due_date: date | None = Field(default=None)
    priority: str | None = Field(default=None)


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    assigned_to: int | None = Field(None, ge=0)
    due_date: date | None = Field(default=None)
    status: str | None = Field(None)
    priority: str | None = Field(None)


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
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        priority=body.priority,
        tenant_id=ctx.tenant_id,
    )
    return {"success": True, "data": task.to_dict(), "message": "任务创建成功"}


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
        tenant_id=ctx.tenant_id,
        status=status,
        assigned_to=assigned_to,
        page=page,
        page_size=page_size,
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
    return {"success": True, "data": task.to_dict(), "message": "获取任务成功"}


@tasks_router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: TaskUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    update_data = body.model_dump(exclude_unset=True)
    task = await service.update_task(tenant_id=ctx.tenant_id, task_id=task_id, **update_data)
    return {"success": True, "data": task.to_dict(), "message": "任务更新成功"}


@tasks_router.post("/tasks/{task_id}/complete", status_code=200)
async def complete_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    task = await service.complete_task(tenant_id=ctx.tenant_id, task_id=task_id)
    return {"success": True, "data": task.to_dict(), "message": "任务已完成"}


@tasks_router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = TaskService(session)
    await service.delete_task(tenant_id=ctx.tenant_id, task_id=task_id)
    return {"success": True, "data": None, "message": "任务已删除"}
