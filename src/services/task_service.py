"""Task service — CRUD via SQLAlchemy ORM."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.task import TaskModel


class TaskService:
    """任务服务 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _ok(task: TaskModel, message: str = "") -> dict:
        return {"success": True, "data": task.to_dict(), "message": message}

    async def create_task(
        self,
        title: str,
        description: str = "",
        assigned_to: int = 0,
        due_date: datetime | None = None,
        tenant_id: int = 0,
        **kwargs,
    ) -> dict:
        now = datetime.now(UTC)
        task = TaskModel(
            tenant_id=tenant_id,
            title=title,
            description=description,
            assigned_to=assigned_to or 0,
            due_date=due_date if isinstance(due_date, datetime) else None,
            status="pending",
            priority=kwargs.get("priority", "normal"),
            created_by=kwargs.get("created_by") or 0,
            created_at=now,
            updated_at=now,
        )
        if due_date is not None and not isinstance(due_date, datetime):
            task.due_date = datetime.combine(due_date, datetime.min.time(), tzinfo=UTC)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        await self.session.commit()
        return self._ok(task, "任务创建成功")

    async def _fetch(self, task_id: int) -> TaskModel | None:
        result = await self.session.execute(select(TaskModel).where(TaskModel.id == task_id))
        return result.scalar_one_or_none()

    async def get_task(self, task_id: int) -> dict:
        task = await self._fetch(task_id)
        if task is None:
            return {"success": False, "data": None, "message": "任务不存在"}
        return {"success": True, "data": task.to_dict(), "message": ""}

    async def update_task(self, task_id: int, **kwargs) -> dict:
        task = await self._fetch(task_id)
        if task is None:
            return {"success": False, "data": None, "message": "任务不存在"}

        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key in ("title", "description", "assigned_to", "status", "priority"):
            if key in kwargs:
                update_values[key] = kwargs[key]
        if "due_date" in kwargs:
            due = kwargs["due_date"]
            if due is None:
                update_values["due_date"] = None
            elif isinstance(due, datetime):
                update_values["due_date"] = due
            else:
                update_values["due_date"] = datetime.combine(due, datetime.min.time(), tzinfo=UTC)

        await self.session.execute(update(TaskModel).where(TaskModel.id == task_id).values(**update_values))
        await self.session.commit()

        refreshed = await self._fetch(task_id)
        return self._ok(refreshed, "任务更新成功")

    async def complete_task(self, task_id: int) -> dict:
        task = await self._fetch(task_id)
        if task is None:
            return {"success": False, "data": None, "message": "任务不存在"}
        now = datetime.now(UTC)
        await self.session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(status="completed", completed_at=now, updated_at=now)
        )
        await self.session.commit()
        refreshed = await self._fetch(task_id)
        return self._ok(refreshed, "任务已完成")

    async def delete_task(self, task_id: int) -> dict:
        task = await self._fetch(task_id)
        if task is None:
            return {"success": False, "data": None, "message": "任务不存在"}
        await self.session.execute(delete(TaskModel).where(TaskModel.id == task_id))
        await self.session.commit()
        return {"success": True, "data": {"id": task_id}, "message": "任务删除成功"}

    async def list_tasks(
        self,
        assigned_to: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        conditions = []
        if assigned_to is not None:
            conditions.append(TaskModel.assigned_to == assigned_to)
        if status:
            conditions.append(TaskModel.status == status)

        count_stmt = select(func.count(TaskModel.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = select(TaskModel).order_by(TaskModel.created_at.desc()).offset(offset).limit(page_size)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await self.session.execute(stmt)
        items = [t.to_dict() for t in result.scalars().all()]
        return {
            "success": True,
            "data": {"page": page, "page_size": page_size, "total": total, "items": items},
            "message": "",
        }

    async def get_my_tasks(self, user_id: int, status: str | None = None) -> list[dict]:
        conditions = [TaskModel.assigned_to == user_id]
        if status:
            conditions.append(TaskModel.status == status)
        result = await self.session.execute(
            select(TaskModel).where(and_(*conditions)).order_by(TaskModel.due_date.asc().nullslast())
        )
        return [t.to_dict() for t in result.scalars().all()]
