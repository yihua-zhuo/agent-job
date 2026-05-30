"""Agent task service — CRUD via SQLAlchemy ORM."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.agent_tasks import AgentTaskModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class AgentTaskStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, description: str, tenant_id: int) -> AgentTaskModel:
        if not description or not description.strip():
            raise ValidationException("description cannot be empty")
        now = datetime.now(UTC)
        task = AgentTaskModel(
            task_id=f"atask_{uuid.uuid4().hex[:16]}",
            tenant_id=tenant_id,
            description=description.strip(),
            status=AgentTaskStatus.PENDING,
            subtasks=[],
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: int, tenant_id: int) -> AgentTaskModel:
        result = await self.session.execute(
            select(AgentTaskModel).where(
                and_(
                    AgentTaskModel.id == task_id,
                    AgentTaskModel.tenant_id == tenant_id,
                )
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundException("AgentTask")
        return task

    async def list_tasks(
        self,
        tenant_id: int,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentTaskModel], int]:
        conditions = [AgentTaskModel.tenant_id == tenant_id]
        if status is not None:
            if status not in tuple(AgentTaskStatus):
                raise ValidationException(f"invalid status: {status!r}")
            conditions.append(AgentTaskModel.status == status)
        if date_from is not None:
            conditions.append(AgentTaskModel.created_at >= date_from)
        if date_to is not None:
            conditions.append(AgentTaskModel.created_at <= date_to)

        count_result = await self.session.execute(
            select(func.count(AgentTaskModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(AgentTaskModel)
            .where(and_(*conditions))
            .order_by(AgentTaskModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


__all__ = ["AgentTaskService"]
