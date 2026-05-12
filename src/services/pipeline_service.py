"""Pipeline service layer - handles pipeline and stage CRUD via PostgreSQL/SQLAlchemy async."""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.pipeline import PipelineModel
from db.models.pipeline_stage import PipelineStageModel
from pkg.errors.app_exceptions import ConflictException, NotFoundException, ValidationException


class PipelineService:
    """Pipeline service backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession):
        self.session = session

    DEFAULT_STAGES = ["lead", "qualified", "proposal", "negotiation", "closed_won"]

    # -------------------------------------------------------------------------
    # Pipeline CRUD
    # -------------------------------------------------------------------------

    async def create_pipeline(self, tenant_id: int, data: dict, created_by: int = 0) -> PipelineModel:
        if not data.get("name"):
            raise ValidationException("管道名称不能为空")

        existing = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.tenant_id == tenant_id,
                PipelineModel.name == data["name"],
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException("管道名称已存在")

        now = datetime.now(UTC)
        pipeline = PipelineModel(
            tenant_id=tenant_id,
            name=data["name"],
            is_default=data.get("is_default", False),
            created_at=now,
            updated_at=now,
        )
        self.session.add(pipeline)
        await self.session.flush()

        stage_names = data.get("stages", self.DEFAULT_STAGES)
        for idx, name in enumerate(stage_names):
            self.session.add(
                PipelineStageModel(
                    pipeline_id=pipeline.id,
                    name=name,
                    display_order=idx,
                    created_at=now,
                )
            )

        result = await self.session.execute(select(PipelineModel).where(PipelineModel.id == pipeline.id))
        return result.scalar_one()

    async def get_pipeline(self, tenant_id: int, pipeline_id: int) -> PipelineModel:
        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            raise NotFoundException("管道")
        return pipeline

    async def get_pipeline_stages(self, pipeline_id: int) -> list[PipelineStageModel]:
        result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        return result.scalars().all()

    async def list_pipelines(
        self, tenant_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[PipelineModel], int]:
        count_result = await self.session.execute(
            select(func.count(PipelineModel.id)).where(PipelineModel.tenant_id == tenant_id)
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(PipelineModel)
            .where(PipelineModel.tenant_id == tenant_id)
            .order_by(PipelineModel.id)
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def update_pipeline(self, tenant_id: int, pipeline_id: int, data: dict) -> PipelineModel:
        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            raise NotFoundException("管道")

        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key in ["name", "is_default"]:
            if key in data:
                update_values[key] = data[key]

        if "name" in update_values:
            dup = await self.session.execute(
                select(PipelineModel).where(
                    PipelineModel.tenant_id == tenant_id,
                    PipelineModel.name == update_values["name"],
                    PipelineModel.id != pipeline_id,
                )
            )
            if dup.scalar_one_or_none():
                raise ConflictException("管道名称已存在")

        await self.session.execute(update(PipelineModel).where(PipelineModel.id == pipeline_id).values(**update_values))

        refreshed = await self.session.execute(select(PipelineModel).where(PipelineModel.id == pipeline_id))
        return refreshed.scalar_one()

    async def delete_pipeline(self, tenant_id: int, pipeline_id: int) -> int:
        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise NotFoundException("管道")

        await self.session.execute(
            delete(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )

        return pipeline_id

    # -------------------------------------------------------------------------
    # Stage CRUD (pipeline-scoped)
    # -------------------------------------------------------------------------

    async def _verify_pipeline(self, tenant_id: int, pipeline_id: int) -> PipelineModel:
        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            raise NotFoundException("管道")
        return pipeline

    async def add_stage(self, tenant_id: int, pipeline_id: int, data: dict) -> PipelineStageModel:
        await self._verify_pipeline(tenant_id, pipeline_id)

        stage_name = data.get("name")
        if not stage_name:
            raise ValidationException("阶段名称不能为空")

        max_order_result = await self.session.execute(
            select(func.max(PipelineStageModel.display_order)).where(PipelineStageModel.pipeline_id == pipeline_id)
        )
        max_order = max_order_result.scalar() or -1

        stage = PipelineStageModel(
            pipeline_id=pipeline_id,
            name=stage_name,
            display_order=max_order + 1,
            created_at=datetime.now(UTC),
        )
        self.session.add(stage)
        await self.session.flush()
        return stage

    async def update_stage(self, tenant_id: int, pipeline_id: int, stage_id: int, data: dict) -> PipelineStageModel:
        await self._verify_pipeline(tenant_id, pipeline_id)

        stage_result = await self.session.execute(
            select(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )
        if not stage_result.scalar_one_or_none():
            raise NotFoundException("阶段")

        update_values: dict = {}
        for key in ["name", "display_order"]:
            if key in data:
                update_values[key] = data[key]

        if update_values:
            await self.session.execute(
                update(PipelineStageModel).where(PipelineStageModel.id == stage_id).values(**update_values)
            )

        refreshed = await self.session.execute(select(PipelineStageModel).where(PipelineStageModel.id == stage_id))
        return refreshed.scalar_one()

    async def delete_stage(self, tenant_id: int, pipeline_id: int, stage_id: int) -> int:
        await self._verify_pipeline(tenant_id, pipeline_id)

        stage_result = await self.session.execute(
            select(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )
        if not stage_result.scalar_one_or_none():
            raise NotFoundException("阶段")

        await self.session.execute(
            delete(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )

        return stage_id

    async def reorder_stages(self, tenant_id: int, pipeline_id: int, stage_ids: list[int]) -> None:
        await self._verify_pipeline(tenant_id, pipeline_id)

        for idx, stage_id in enumerate(stage_ids):
            await self.session.execute(
                update(PipelineStageModel)
                .where(
                    PipelineStageModel.id == stage_id,
                    PipelineStageModel.pipeline_id == pipeline_id,
                )
                .values(display_order=idx)
            )
