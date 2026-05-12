"""Task service — CRUD via SQLAlchemy ORM."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.task import TaskModel
from pkg.errors.app_exceptions import NotFoundException


class TaskService:
    """任务服务 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self,
        title: str,
        description: str = "",
        assigned_to: int = 0,
        due_date: datetime | None = None,
        tenant_id: int = 0,
        **kwargs,
    ) -> TaskModel:
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
        return task

    async def _fetch(self, task_id: int, tenant_id: int) -> TaskModel | None:
        result = await self.session.execute(
            select(TaskModel).where(and_(TaskModel.id == task_id, TaskModel.tenant_id == tenant_id))
        )
        return result.scalar_one_or_none()

    async def get_task(self, tenant_id: int, task_id: int) -> TaskModel:
        task = await self._fetch(task_id, tenant_id)
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    async def update_task(self, tenant_id: int, task_id: int, **kwargs) -> TaskModel:
        task = await self._fetch(task_id, tenant_id)
        if task is None:
            raise NotFoundException("任务不存在")

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

        await self.session.execute(
            update(TaskModel)
            .where(and_(TaskModel.id == task_id, TaskModel.tenant_id == tenant_id))
            .values(**update_values)
        )
        await self.session.commit()

        refreshed = await self._fetch(task_id, tenant_id)
        return refreshed

    async def complete_task(self, tenant_id: int, task_id: int) -> TaskModel:
        task = await self._fetch(task_id, tenant_id)
        if task is None:
            raise NotFoundException("任务不存在")
        now = datetime.now(UTC)
        await self.session.execute(
            update(TaskModel)
            .where(and_(TaskModel.id == task_id, TaskModel.tenant_id == tenant_id))
            .values(status="completed", completed_at=now, updated_at=now)
        )
        await self.session.commit()
        refreshed = await self._fetch(task_id, tenant_id)
        return refreshed

    async def delete_task(self, tenant_id: int, task_id: int) -> TaskModel:
        task = await self._fetch(task_id, tenant_id)
        if task is None:
            raise NotFoundException("任务不存在")
        await self.session.execute(
            delete(TaskModel).where(and_(TaskModel.id == task_id, TaskModel.tenant_id == tenant_id))
        )
        await self.session.commit()
        return task

    async def list_tasks(
        self,
        tenant_id: int,
        assigned_to: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[TaskModel]:
        conditions = [TaskModel.tenant_id == tenant_id]
        if assigned_to is not None:
            conditions.append(TaskModel.assigned_to == assigned_to)
        if status:
            conditions.append(TaskModel.status == status)

        offset = (page - 1) * page_size
        stmt = select(TaskModel).order_by(TaskModel.created_at.desc()).offset(offset).limit(page_size)
        stmt = stmt.where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_my_tasks(self, tenant_id: int, user_id: int, status: str | None = None) -> list[TaskModel]:
        conditions = [TaskModel.tenant_id == tenant_id, TaskModel.assigned_to == user_id]
        if status:
            conditions.append(TaskModel.status == status)
        result = await self.session.execute(
            select(TaskModel).where(and_(*conditions)).order_by(TaskModel.due_date.asc().nullslast())
        )
        return result.scalars().all()
