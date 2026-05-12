"""Activity service — CRUD + search via SQLAlchemy ORM."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from models.activity import Activity, ActivityType
from pkg.errors.app_exceptions import NotFoundException, ValidationException


def _to_activity(row: ActivityModel) -> Activity:
    return Activity(
        id=row.id,
        tenant_id=row.tenant_id,
        customer_id=row.customer_id,
        opportunity_id=row.opportunity_id,
        type=ActivityType(row.type),
        content=row.content or "",
        created_by=row.created_by,
        created_at=row.created_at,
    )


class ActivityService:
    """活动记录服务 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch(self, activity_id: int, tenant_id: int) -> ActivityModel:
        result = await self.session.execute(
            select(ActivityModel).where(and_(ActivityModel.id == activity_id, ActivityModel.tenant_id == tenant_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("活动记录")
        return row

    async def create_activity(
        self,
        customer_id: int,
        activity_type: str,
        content: str,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> Activity:
        try:
            activity_type_enum = ActivityType(activity_type)
        except ValueError:
            raise ValidationException(f"无效的活动类型: {activity_type}")

        now = datetime.now(UTC)
        row = ActivityModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            opportunity_id=kwargs.get("opportunity_id"),
            type=activity_type_enum.value,
            content=content,
            created_by=created_by,
            created_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_activity(row)

    async def get_activity(self, activity_id: int, tenant_id: int = 0) -> Activity:
        return _to_activity(await self._fetch(activity_id, tenant_id))

    async def update_activity(self, activity_id: int, tenant_id: int = 0, **kwargs) -> Activity:
        await self._fetch(activity_id, tenant_id)

        update_values: dict = {}
        if "content" in kwargs:
            update_values["content"] = kwargs["content"]
        if "activity_type" in kwargs:
            try:
                update_values["type"] = ActivityType(kwargs["activity_type"]).value
            except ValueError:
                raise ValidationException(f"无效的活动类型: {kwargs['activity_type']}")
        if "opportunity_id" in kwargs:
            update_values["opportunity_id"] = kwargs["opportunity_id"]

        if update_values:
            await self.session.execute(
                update(ActivityModel).where(ActivityModel.id == activity_id).values(**update_values)
            )
            await self.session.flush()

        return _to_activity(await self._fetch(activity_id, tenant_id))

    async def delete_activity(self, activity_id: int, tenant_id: int = 0) -> dict:
        await self._fetch(activity_id, tenant_id)
        await self.session.execute(
            delete(ActivityModel).where(
                and_(
                    ActivityModel.id == activity_id,
                    ActivityModel.tenant_id == tenant_id,
                )
            )
        )
        await self.session.flush()
        return {"id": activity_id}

    async def list_activities(
        self,
        customer_id: int | None = None,
        activity_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
        tenant_id: int = 0,
    ) -> tuple[list[Activity], int]:
        conditions = [ActivityModel.tenant_id == tenant_id]
        if customer_id is not None:
            conditions.append(ActivityModel.customer_id == customer_id)
        if activity_type:
            conditions.append(ActivityModel.type == activity_type)

        count_result = await self.session.execute(select(func.count(ActivityModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(ActivityModel)
            .where(and_(*conditions))
            .order_by(ActivityModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [_to_activity(row) for row in result.scalars().all()]
        return items, total

    async def get_customer_activities(
        self,
        customer_id: int,
        tenant_id: int = 0,
    ) -> list[Activity]:
        result = await self.session.execute(
            select(ActivityModel)
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.customer_id == customer_id,
                )
            )
            .order_by(ActivityModel.created_at.desc())
        )
        return [_to_activity(row) for row in result.scalars().all()]

    async def get_opportunity_activities(
        self,
        opportunity_id: int,
        tenant_id: int = 0,
    ) -> list[Activity]:
        result = await self.session.execute(
            select(ActivityModel)
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.opportunity_id == opportunity_id,
                )
            )
            .order_by(ActivityModel.created_at.desc())
        )
        return [_to_activity(row) for row in result.scalars().all()]

    async def search_activities(
        self,
        keyword: str,
        tenant_id: int = 0,
        filters: dict | None = None,
    ) -> list[Activity]:
        conditions = [ActivityModel.tenant_id == tenant_id]
        if keyword:
            pattern = f"%{keyword.lower()}%"
            conditions.append(func.lower(ActivityModel.content).like(pattern))
        if filters:
            if "customer_id" in filters:
                conditions.append(ActivityModel.customer_id == filters["customer_id"])
            if "activity_type" in filters:
                conditions.append(ActivityModel.type == filters["activity_type"])
            if "start_date" in filters:
                conditions.append(ActivityModel.created_at >= filters["start_date"])
            if "end_date" in filters:
                conditions.append(ActivityModel.created_at <= filters["end_date"])

        result = await self.session.execute(
            select(ActivityModel).where(and_(*conditions)).order_by(ActivityModel.created_at.desc())
        )
        return [_to_activity(row) for row in result.scalars().all()]

    async def get_activity_summary(
        self,
        customer_id: int,
        tenant_id: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        conditions = [
            ActivityModel.tenant_id == tenant_id,
            ActivityModel.customer_id == customer_id,
        ]
        if start_date is not None:
            conditions.append(ActivityModel.created_at >= start_date)
        if end_date is not None:
            conditions.append(ActivityModel.created_at <= end_date)

        total_result = await self.session.execute(select(func.count(ActivityModel.id)).where(and_(*conditions)))
        total = total_result.scalar() or 0

        by_type_result = await self.session.execute(
            select(ActivityModel.type, func.count(ActivityModel.id))
            .where(and_(*conditions))
            .group_by(ActivityModel.type)
        )
        by_type = {t: count for t, count in by_type_result.all()}

        recent_result = await self.session.execute(
            select(ActivityModel).where(and_(*conditions)).order_by(ActivityModel.created_at.desc()).limit(5)
        )
        recent = [_to_activity(row) for row in recent_result.scalars().all()]

        return {"total": total, "by_type": by_type, "recent_activities": recent}
