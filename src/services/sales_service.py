"""Sales service layer - handles sales pipeline and opportunity logic via PostgreSQL/SQLAlchemy async."""
from datetime import datetime, UTC
from db.connection import get_db_session
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.pipeline import PipelineModel
from db.models.pipeline_stage import PipelineStageModel
from db.models.opportunity import OpportunityModel
from models.response import ApiResponse
from models.opportunity import Stage as OpportunityStage


class SalesService:
    """Sales service backed by PostgreSQL via SQLAlchemy async."""

    DEFAULT_STAGES = ["lead", "qualified", "proposal", "negotiation", "closed_won"]

    def __init__(self, session: AsyncSession = None):
        self._session_context = None
        if session is None:
            context = get_db_session()
            try:
                session = context.__enter__()
                self._session_context = context
            except (AttributeError, TypeError):
                # sync __enter__ not supported — leave session=None
                # (async context callers must pass session explicitly)
                session = None
                self._session_context = None
        else:
            self._session_context = None
        self.session = session
        self.session = session

    # -------------------------------------------------------
    # 管道 (Pipeline) 操作
    # -------------------------------------------------------

    async def create_pipeline(self, tenant_id: int, data: dict) -> ApiResponse:
        """创建新的销售管道 / Create a new sales pipeline."""
        if not data.get("name"):
            return ApiResponse.error(message="管道名称不能为空", code=3001)

        # 检查同名管道是否已存在
        existing = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.tenant_id == tenant_id,
                PipelineModel.name == data["name"],
            )
        )
        if existing.scalar_one_or_none():
            return ApiResponse.error(message="管道名称已存在", code=3002)

        # 创建管道记录
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

        # 创建管道阶段
        stages_data = data.get("stages", self.DEFAULT_STAGES)
        for idx, stage_name in enumerate(stages_data):
            stage = PipelineStageModel(
                pipeline_id=pipeline_id,
                name=stage_name,
                display_order=idx,
                created_at=now,
            )
            self.session.add(stage)

        await self.session.commit()

        # 查询完整管道及阶段数据用于返回
        result = await self.session.execute(
            select(PipelineModel).where(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one()
        stages_result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        stages = [s.name for s in stages_result.scalars().all()]

        return ApiResponse.success(
            data={
                "id": pipeline.id,
                "tenant_id": pipeline.tenant_id,
                "name": pipeline.name,
                "is_default": pipeline.is_default,
                "stages": stages,
                "created_at": pipeline.created_at.isoformat(),
                "updated_at": pipeline.updated_at.isoformat(),
            },
            message="管道创建成功",
        )

    async def list_pipelines(self, tenant_id: int) -> ApiResponse:
        """列出当前租户的所有管道 / List all pipelines for tenant."""
        result = await self.session.execute(
            select(PipelineModel)
            .where(PipelineModel.tenant_id == tenant_id)
            .order_by(PipelineModel.id)
        )
        pipelines = result.scalars().all()

        items = []
        for p in pipelines:
            stages_result = await self.session.execute(
                select(PipelineStageModel)
                .where(PipelineStageModel.pipeline_id == p.id)
                .order_by(PipelineStageModel.display_order)
            )
            stages = [s.name for s in stages_result.scalars().all()]
            items.append({
                "id": p.id,
                "tenant_id": p.tenant_id,
                "name": p.name,
                "is_default": p.is_default,
                "stages": stages,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            })

        return ApiResponse.success(data={"items": items}, message="")

    async def get_pipeline(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """根据 ID 获取管道 / Get pipeline by ID."""
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
        stages = [s.name for s in stages_result.scalars().all()]

        return ApiResponse.success(
            data={
                "id": pipeline.id,
                "tenant_id": pipeline.tenant_id,
                "name": pipeline.name,
                "is_default": pipeline.is_default,
                "stages": stages,
                "created_at": pipeline.created_at.isoformat(),
                "updated_at": pipeline.updated_at.isoformat(),
            },
            message="",
        )

    async def get_pipeline_stats(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """获取管道统计信息（总数/赢单/输单）/ Get pipeline statistics."""
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        # 统计总数
        total_result = await self.session.execute(
            select(func.count(OpportunityModel.id)).where(
                OpportunityModel.pipeline_id == pipeline_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        total = total_result.scalar() or 0

        # 赢单数
        won_result = await self.session.execute(
            select(func.count(OpportunityModel.id)).where(
                OpportunityModel.pipeline_id == pipeline_id,
                OpportunityModel.tenant_id == tenant_id,
                OpportunityModel.stage == OpportunityStage.CLOSED_WON.value,
            )
        )
        won = won_result.scalar() or 0

        # 输单数
        lost_result = await self.session.execute(
            select(func.count(OpportunityModel.id)).where(
                OpportunityModel.pipeline_id == pipeline_id,
                OpportunityModel.tenant_id == tenant_id,
                OpportunityModel.stage == OpportunityStage.CLOSED_LOST.value,
            )
        )
        lost = lost_result.scalar() or 0

        return ApiResponse.success(
            data={"pipeline_id": pipeline_id, "total": total, "won": won, "lost": lost},
            message="",
        )

    async def get_pipeline_funnel(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """获取管道漏斗（各阶段商机数量）/ Get pipeline funnel (stage distribution)."""
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        # 加载管道阶段列表作为漏斗顺序
        stages_result = await self.session.execute(
            select(PipelineStageModel)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .order_by(PipelineStageModel.display_order)
        )
        pipeline_stages = [s.name for s in stages_result.scalars().all()]
        if not pipeline_stages:
            pipeline_stages = self.DEFAULT_STAGES

        # 初始化计数
        stage_counts = {stage: 0 for stage in pipeline_stages}

        # 按阶段分组统计
        count_result = await self.session.execute(
            select(
                OpportunityModel.stage,
                func.count(OpportunityModel.id).label("opp_count"),
            )
            .where(
                OpportunityModel.pipeline_id == pipeline_id,
                OpportunityModel.tenant_id == tenant_id,
            )
            .group_by(OpportunityModel.stage)
        )
        for row in count_result.all():
            stage_name = row.stage
            if stage_name in stage_counts:
                stage_counts[stage_name] = row.opp_count

        return ApiResponse.success(
            data={"pipeline_id": pipeline_id, "stages": stage_counts},
            message="",
        )

    # -------------------------------------------------------
    # 商机 (Opportunity) 操作
    # -------------------------------------------------------

    async def create_opportunity(self, tenant_id: int, data: dict) -> ApiResponse:
        """创建新的商机 / Create a new opportunity."""
        required = ["name", "customer_id", "pipeline_id", "stage", "amount", "owner_id"]
        for field in required:
            if not data.get(field):
                return ApiResponse.error(message=f"缺少必填字段: {field}", code=1002)

        try:
            amount = Decimal(str(data["amount"]))
            probability = int(data.get("probability", 0))
            expected_close = datetime.fromisoformat(
                data.get("expected_close_date", datetime.now(UTC).isoformat())
            )
            stage = (
                OpportunityStage(data["stage"]).value
                if isinstance(data["stage"], str)
                else data["stage"]
            )
        except (ValueError, TypeError) as e:
            return ApiResponse.error(message=f"字段格式错误: {e}", code=1001)

        pipeline_id_val = int(data["pipeline_id"])

        # 验证管道归属
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(
                PipelineModel.id == pipeline_id_val,
                PipelineModel.tenant_id == tenant_id,
            )
        )
        if not pipeline_result.scalar_one_or_none():
            return ApiResponse.error(message="管道不存在", code=3001)

        now = datetime.now(UTC)
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=int(data["customer_id"]),
            name=data["name"],
            stage=stage,
            amount=amount,
            probability=probability,
            expected_close_date=expected_close,
            owner_id=int(data["owner_id"]),
            pipeline_id=pipeline_id_val,
            created_at=now,
            updated_at=now,
        )
        self.session.add(opp)
        await self.session.flush()

        return ApiResponse.success(
            data={
                "id": opp.id,
                "tenant_id": opp.tenant_id,
                "customer_id": opp.customer_id,
                "name": opp.name,
                "stage": opp.stage,
                "amount": str(opp.amount),
                "probability": opp.probability,
                "expected_close_date": (
                    opp.expected_close_date.isoformat()
                    if opp.expected_close_date
                    else None
                ),
                "owner_id": opp.owner_id,
                "pipeline_id": opp.pipeline_id,
                "created_at": opp.created_at.isoformat(),
                "updated_at": opp.updated_at.isoformat(),
            },
            message="商机创建成功",
        )

    async def list_opportunities(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        pipeline_id: Optional[int] = None,
        stage: Optional[str] = None,
        owner_id: Optional[int] = None,
    ) -> ApiResponse:
        """列出商机，支持分页和过滤 / List opportunities with filters."""
        if tenant_id <= 0:
            return ApiResponse.error(message="无效的租户ID", code=1404)

        # 构造基础查询条件
        base_where = [OpportunityModel.tenant_id == tenant_id]
        if pipeline_id is not None:
            base_where.append(OpportunityModel.pipeline_id == pipeline_id)
        if stage is not None:
            stage_val = (
                OpportunityStage(stage).value
                if isinstance(stage, str)
                else stage
            )
            base_where.append(OpportunityModel.stage == stage_val)
        if owner_id is not None:
            base_where.append(OpportunityModel.owner_id == owner_id)

        # 统计总数
        count_result = await self.session.execute(
            select(func.count(OpportunityModel.id)).where(*base_where)
        )
        total = count_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(OpportunityModel)
            .where(*base_where)
            .order_by(OpportunityModel.id)
            .offset(offset)
            .limit(page_size)
        )
        opps = result.scalars().all()

        items = [
            {
                "id": o.id,
                "tenant_id": o.tenant_id,
                "customer_id": o.customer_id,
                "name": o.name,
                "stage": o.stage,
                "amount": str(o.amount),
                "probability": o.probability,
                "expected_close_date": (
                    o.expected_close_date.isoformat()
                    if o.expected_close_date
                    else None
                ),
                "owner_id": o.owner_id,
                "pipeline_id": o.pipeline_id,
                "created_at": o.created_at.isoformat(),
                "updated_at": o.updated_at.isoformat(),
            }
            for o in opps
        ]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="",
        )

    async def get_opportunity(self, tenant_id: int, opp_id: int) -> ApiResponse:
        """根据 ID 获取商机 / Get opportunity by ID."""
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opp_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return ApiResponse.error(message="商机不存在", code=3001)

        return ApiResponse.success(
            data={
                "id": opp.id,
                "tenant_id": opp.tenant_id,
                "customer_id": opp.customer_id,
                "name": opp.name,
                "stage": opp.stage,
                "amount": str(opp.amount),
                "probability": opp.probability,
                "expected_close_date": (
                    opp.expected_close_date.isoformat()
                    if opp.expected_close_date
                    else None
                ),
                "owner_id": opp.owner_id,
                "pipeline_id": opp.pipeline_id,
                "created_at": opp.created_at.isoformat(),
                "updated_at": opp.updated_at.isoformat(),
            },
            message="",
        )

    async def update_opportunity(
        self, tenant_id: int, opp_id: int, data: dict
    ) -> ApiResponse:
        """更新商机字段 / Update opportunity fields."""
        # 先验证归属
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opp_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return ApiResponse.error(message="商机不存在", code=3001)

        # 构建更新字段
        update_values: dict = {"updated_at": datetime.now(UTC)}

        for key in ["name", "customer_id", "owner_id"]:
            if key in data:
                update_values[key] = data[key]

        if "amount" in data:
            try:
                update_values["amount"] = Decimal(str(data["amount"]))
            except (ValueError, TypeError):
                return ApiResponse.error(message="amount 格式错误", code=1001)

        if "probability" in data:
            try:
                update_values["probability"] = int(data["probability"])
            except (ValueError, TypeError):
                return ApiResponse.error(message="probability 格式错误", code=1001)

        if "stage" in data:
            try:
                stage_val = (
                    OpportunityStage(data["stage"]).value
                    if isinstance(data["stage"], str)
                    else data["stage"]
                )
                update_values["stage"] = stage_val
            except ValueError:
                return ApiResponse.error(message="stage 值无效", code=1001)

        if "expected_close_date" in data:
            try:
                update_values["expected_close_date"] = datetime.fromisoformat(
                    data["expected_close_date"]
                )
            except (ValueError, TypeError):
                return ApiResponse.error(
                    message="expected_close_date 格式错误", code=1001
                )

        # 执行 UPDATE ... WHERE id=? AND tenant_id=?
        await self.session.execute(
            update(OpportunityModel)
            .where(
                OpportunityModel.id == opp_id,
                OpportunityModel.tenant_id == tenant_id,
            )
            .values(**update_values)
        )
        await self.session.commit()

        # 查询更新后的记录
        refreshed = await self.session.execute(
            select(OpportunityModel).where(OpportunityModel.id == opp_id)
        )
        opp = refreshed.scalar_one()

        return ApiResponse.success(
            data={
                "id": opp.id,
                "tenant_id": opp.tenant_id,
                "customer_id": opp.customer_id,
                "name": opp.name,
                "stage": opp.stage,
                "amount": str(opp.amount),
                "probability": opp.probability,
                "expected_close_date": (
                    opp.expected_close_date.isoformat()
                    if opp.expected_close_date
                    else None
                ),
                "owner_id": opp.owner_id,
                "pipeline_id": opp.pipeline_id,
                "created_at": opp.created_at.isoformat(),
                "updated_at": opp.updated_at.isoformat(),
            },
            message="商机更新成功",
        )

    async def change_stage(self, tenant_id: int, opp_id: int, stage: str) -> ApiResponse:
        """变更商机阶段 / Change opportunity stage."""
        try:
            stage_val = OpportunityStage(stage).value
        except ValueError:
            return ApiResponse.error(message="stage 值无效", code=1001)

        # 验证归属
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opp_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            return ApiResponse.error(message="商机不存在", code=3001)

        # UPDATE ... WHERE id=? AND tenant_id=?
        await self.session.execute(
            update(OpportunityModel)
            .where(
                OpportunityModel.id == opp_id,
                OpportunityModel.tenant_id == tenant_id,
            )
            .values(stage=stage_val, updated_at=datetime.now(UTC))
        )
        await self.session.commit()

        return ApiResponse.success(
            data={"id": opp_id, "stage": stage_val},
            message="阶段更新成功",
        )

    async def get_forecast(self, tenant_id: int, owner_id: int = None) -> ApiResponse:
        """按负责人获取销售预测 / Get sales forecast by owner."""
        # 获取当前租户所有管道
        pipeline_result = await self.session.execute(
            select(PipelineModel).where(PipelineModel.tenant_id == tenant_id)
        )
        pipelines = pipeline_result.scalars().all()
        pipeline_ids = [p.id for p in pipelines]

        if not pipeline_ids:
            return ApiResponse.success(
                data={"owner_id": owner_id, "forecast": {}},
                message="",
            )

        # 基础过滤条件（排除 closed_won 和 closed_lost）
        base_where = [
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.pipeline_id.in_(pipeline_ids),
            OpportunityModel.stage.notin_([
                OpportunityStage.CLOSED_WON.value,
                OpportunityStage.CLOSED_LOST.value,
            ]),
        ]
        if owner_id is not None:
            base_where.append(OpportunityModel.owner_id == owner_id)

        # 按管道分组统计金额
        forecast_result = await self.session.execute(
            select(
                OpportunityModel.pipeline_id,
                func.sum(OpportunityModel.amount).label("total_amount"),
            )
            .where(*base_where)
            .group_by(OpportunityModel.pipeline_id)
        )
        pipeline_forecasts = {
            row.pipeline_id: float(row.total_amount or 0)
            for row in forecast_result.all()
        }

        return ApiResponse.success(
            data={"owner_id": owner_id, "forecast": pipeline_forecasts},
            message="",
        )