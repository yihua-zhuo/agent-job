"""Pipeline service layer - handles pipeline and stage CRUD via PostgreSQL/SQLAlchemy async."""
from datetime import datetime, UTC
from typing import Optional, List

from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.pipeline import PipelineModel
from db.models.pipeline_stage import PipelineStageModel
from models.response import ApiResponse


class PipelineService:
    """Pipeline service backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _require_session(self):
        pass

    DEFAULT_STAGES = ["lead", "qualified", "proposal", "negotiation", "closed_won"]

    # -------------------------------------------------------------------------
    # Pipeline CRUD
    # -------------------------------------------------------------------------

    async def create_pipeline(
        self, tenant_id: int, data: dict, created_by: int = 0
    ) -> ApiResponse:
        """Create a new pipeline with stages."""

        if not data.get("name"):
            return ApiResponse.error(message="管道名称不能为空", code=3001)

        # Check for duplicate name within tenant
        existing = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.tenant_id == tenant_id,
                PipelineModel.name == data["name"],
            )
        )
        if existing.scalar_one_or_none():
            return ApiResponse.error(message="管道名称已存在", code=3002)

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
        pipeline_id = pipeline.id

        # Create default or custom stages
        stage_names = data.get("stages", self.DEFAULT_STAGES)
        for idx, name in enumerate(stage_names):
            stage = PipelineStageModel(
                pipeline_id=pipeline_id,
                name=name,
                display_order=idx,
                created_at=now,
            )
            self.session.add(stage)

        await self.session.commit()

        # Reload pipeline with stages for response
        result = await self.session.execute(
            select(PipelineModel).where(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one()
        stages_result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        stages = [s.to_dict() for s in stages_result.scalars().all()]

        return ApiResponse.success(
            data={
                **pipeline.to_dict(),
                "stages": stages,
            },
            message="管道创建成功",
        )

    async def get_pipeline(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """Get a pipeline by ID (tenant-scoped)."""

        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            return ApiResponse.error(message="管道不存在", code=3001)

        stages_result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        stages = [s.to_dict() for s in stages_result.scalars().all()]

        return ApiResponse.success(
            data={**pipeline.to_dict(), "stages": stages},
            message="",
        )

    async def list_pipelines(
        self, tenant_id: int, page: int = 1, page_size: int = 20
    ) -> ApiResponse:
        """List all pipelines for a tenant with pagination."""

        # Count
        count_result = await self.session.execute(
            select(func.count(PipelineModel.id)).where(
                PipelineModel.tenant_id == tenant_id
            )
        )
        total = count_result.scalar() or 0

        # Data
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(PipelineModel)
            .where(PipelineModel.tenant_id == tenant_id)
            .order_by(PipelineModel.id)
            .offset(offset)
            .limit(page_size)
        )
        pipelines = result.scalars().all()

        items = []
        for p in pipelines:
            stages_result = await self.session.execute(
                select(PipelineStageModel)
                .where(PipelineStageModel.pipeline_id == p.id)
                .order_by(PipelineStageModel.display_order)
            )
            stages = [s.to_dict() for s in stages_result.scalars().all()]
            items.append({**p.to_dict(), "stages": stages})

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="",
        )

    async def update_pipeline(
        self, tenant_id: int, pipeline_id: int, data: dict
    ) -> ApiResponse:
        """Update pipeline fields (tenant-scoped)."""

        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            return ApiResponse.error(message="管道不存在", code=3001)

        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key in ["name", "is_default"]:
            if key in data:
                update_values[key] = data[key]

        if "name" in update_values:
            # Check duplicate name
            dup = await self.session.execute(
                select(PipelineModel).where(
                    PipelineModel.tenant_id == tenant_id,
                    PipelineModel.name == update_values["name"],
                    PipelineModel.id != pipeline_id,
                )
            )
            if dup.scalar_one_or_none():
                return ApiResponse.error(message="管道名称已存在", code=3002)

        await self.session.execute(
            update(PipelineModel)
            .where(PipelineModel.id == pipeline_id)
            .values(**update_values)
        )
        await self.session.commit()

        refreshed = await self.session.execute(
            select(PipelineModel).where(PipelineModel.id == pipeline_id)
        )
        pipeline = refreshed.scalar_one()
        stages_result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        stages = [s.to_dict() for s in stages_result.scalars().all()]

        return ApiResponse.success(
            data={**pipeline.to_dict(), "stages": stages},
            message="管道更新成功",
        )

    async def delete_pipeline(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """Delete a pipeline and its stages (tenant-scoped)."""

        result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        await self.session.execute(
            delete(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        await self.session.commit()

        return ApiResponse.success(message="管道删除成功")

    # -------------------------------------------------------------------------
    # Stage CRUD (pipeline-scoped)
    # -------------------------------------------------------------------------

    async def add_stage(
        self, tenant_id: int, pipeline_id: int, data: dict
    ) -> ApiResponse:
        """Add a stage to a pipeline."""

        # Verify pipeline belongs to tenant
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        stage_name = data.get("name")
        if not stage_name:
            return ApiResponse.error(message="阶段名称不能为空", code=1001)

        # Get current max display_order
        max_order_result = await self.session.execute(
            select(func.max(PipelineStageModel.display_order)).where(
                PipelineStageModel.pipeline_id == pipeline_id
            )
        )
        max_order = max_order_result.scalar() or -1

        stage = PipelineStageModel(
            pipeline_id=pipeline_id,
            name=stage_name,
            display_order=max_order + 1,
            created_at=datetime.now(UTC),
        )
        self.session.add(stage)
        await self.session.commit()

        return ApiResponse.success(
            data=stage.to_dict(),
            message="阶段添加成功",
        )

    async def update_stage(
        self, tenant_id: int, pipeline_id: int, stage_id: int, data: dict
    ) -> ApiResponse:
        """Update a pipeline stage (tenant-scoped)."""

        # Verify tenant owns the pipeline
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        stage_result = await self.session.execute(
            select(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )
        stage = stage_result.scalar_one_or_none()
        if not stage:
            return ApiResponse.error(message="阶段不存在", code=3001)

        update_values: dict = {}
        for key in ["name", "display_order"]:
            if key in data:
                update_values[key] = data[key]

        if update_values:
            await self.session.execute(
                update(PipelineStageModel)
                .where(PipelineStageModel.id == stage_id)
                .values(**update_values)
            )
            await self.session.commit()

        refreshed = await self.session.execute(
            select(PipelineStageModel).where(PipelineStageModel.id == stage_id)
        )
        stage = refreshed.scalar_one()

        return ApiResponse.success(
            data=stage.to_dict(),
            message="阶段更新成功",
        )

    async def delete_stage(
        self, tenant_id: int, pipeline_id: int, stage_id: int
    ) -> ApiResponse:
        """Delete a stage from a pipeline (tenant-scoped)."""

        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        stage_result = await self.session.execute(
            select(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )
        if not stage_result.scalar_one_or_none():
            return ApiResponse.error(message="阶段不存在", code=3001)

        await self.session.execute(
            delete(PipelineStageModel).where(
                PipelineStageModel.id == stage_id,
                PipelineStageModel.pipeline_id == pipeline_id,
            )
        )
        await self.session.commit()

        return ApiResponse.success(message="阶段删除成功")

    async def reorder_stages(
        self, tenant_id: int, pipeline_id: int, stage_ids: List[int]
    ) -> ApiResponse:
        """Reorder pipeline stages by assigning display_order from the stage_ids list."""
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        for idx, stage_id in enumerate(stage_ids):
            await self.session.execute(
                update(PipelineStageModel)
                .where(
                    PipelineStageModel.id == stage_id,
                    PipelineStageModel.pipeline_id == pipeline_id,
                )
                .values(display_order=idx)
            )

        await self.session.commit()
        return ApiResponse.success(message="阶段顺序更新成功")