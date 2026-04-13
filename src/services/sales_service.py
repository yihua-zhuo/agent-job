"""Sales service layer - handles sales pipeline and opportunity logic."""
from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal
from src.models.response import ApiResponse
from src.models.pipeline import Pipeline
from src.models.opportunity import Opportunity, Stage


class SalesService:
    """Sales service with in-memory storage"""

    def __init__(self):
        self._pipelines: Dict[int, Pipeline] = {}
        self._opportunities: Dict[int, Opportunity] = {}
        self._next_pipeline_id = 1
        self._next_opp_id = 1

    def create_pipeline(self, tenant_id: int, data: dict) -> ApiResponse:
        """Create a new sales pipeline"""
        if not data.get('name'):
            return ApiResponse.error(message="管道名称不能为空", code=3001)

        stages_data = data.get('stages', ['lead', 'qualified', 'proposal', 'negotiation', 'closed_won'])
        stages = [Stage(s) if isinstance(s, str) else s for s in stages_data]

        pipeline = Pipeline(
            id=self._next_pipeline_id,
            tenant_id=tenant_id,
            name=data['name'],
            stages=stages,
            is_default=data.get('is_default', False),
        )
        self._pipelines[self._next_pipeline_id] = pipeline
        self._next_pipeline_id += 1
        return ApiResponse.success(data=pipeline.to_dict(), message="管道创建成功")

    def list_pipelines(self, tenant_id: int) -> ApiResponse:
        """List all pipelines for tenant"""
        items = [p.to_dict() for p in self._pipelines.values() if p.tenant_id == tenant_id]
        return ApiResponse.success(data={"items": items}, message="")

    def get_pipeline(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """Get pipeline by ID"""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.tenant_id != tenant_id:
            return ApiResponse.error(message="管道不存在", code=3001)
        return ApiResponse.success(data=pipeline.to_dict(), message="")

    def get_pipeline_stats(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """Get pipeline statistics"""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.tenant_id != tenant_id:
            return ApiResponse.error(message="管道不存在", code=3001)

        pipeline_opps = [o for o in self._opportunities.values() if o.pipeline_id == pipeline_id and o.tenant_id == tenant_id]

        total = len(pipeline_opps)
        won = len([o for o in pipeline_opps if o.stage == Stage.CLOSED_WON])
        lost = len([o for o in pipeline_opps if o.stage == Stage.CLOSED_LOST])

        return ApiResponse.success(
            data={"pipeline_id": pipeline_id, "total": total, "won": won, "lost": lost},
            message=""
        )

    def get_pipeline_funnel(self, tenant_id: int, pipeline_id: int) -> ApiResponse:
        """Get pipeline funnel (stage distribution)"""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.tenant_id != tenant_id:
            return ApiResponse.error(message="管道不存在", code=3001)

        stage_counts = {}
        for stage in pipeline.stages:
            stage_name = stage.value if isinstance(stage, Stage) else stage
            stage_counts[stage_name] = 0

        for opp in self._opportunities.values():
            if opp.pipeline_id == pipeline_id and opp.tenant_id == tenant_id:
                stage_name = opp.stage.value if isinstance(opp.stage, Stage) else opp.stage
                if stage_name in stage_counts:
                    stage_counts[stage_name] += 1

        return ApiResponse.success(
            data={"pipeline_id": pipeline_id, "stages": stage_counts},
            message=""
        )

    def create_opportunity(self, tenant_id: int, data: dict) -> ApiResponse:
        """Create a new opportunity"""
        required = ['name', 'customer_id', 'pipeline_id', 'stage', 'amount', 'owner_id']
        for field in required:
            if not data.get(field):
                return ApiResponse.error(message=f"缺少必填字段: {field}", code=1002)

        try:
            amount = Decimal(str(data['amount']))
            probability = int(data.get('probability', 0))
            expected_close = datetime.fromisoformat(data.get('expected_close_date', datetime.utcnow().isoformat()))
            stage = Stage(data['stage']) if isinstance(data['stage'], str) else data['stage']
        except (ValueError, TypeError) as e:
            return ApiResponse.error(message=f"字段格式错误: {e}", code=1001)

        pipeline = self._pipelines.get(int(data['pipeline_id']))
        if not pipeline or pipeline.tenant_id != tenant_id:
            return ApiResponse.error(message="管道不存在", code=3001)

        opp = Opportunity(
            id=self._next_opp_id,
            tenant_id=tenant_id,
            customer_id=int(data['customer_id']),
            name=data['name'],
            stage=stage,
            amount=amount,
            probability=probability,
            expected_close_date=expected_close,
            owner_id=int(data['owner_id']),
            pipeline_id=int(data['pipeline_id']),
        )
        self._opportunities[self._next_opp_id] = opp
        self._next_opp_id += 1
        return ApiResponse.success(data=opp.to_dict(), message="商机创建成功")

    def list_opportunities(self, tenant_id: int, page=1, page_size=20, pipeline_id=None, stage=None, owner_id=None) -> ApiResponse:
        """List opportunities with filters"""
        filtered = [o for o in self._opportunities.values() if o.tenant_id == tenant_id]

        if pipeline_id:
            filtered = [o for o in filtered if o.pipeline_id == pipeline_id]
        if stage:
            stage_enum = Stage(stage) if isinstance(stage, str) else stage
            filtered = [o for o in filtered if o.stage == stage_enum]
        if owner_id:
            filtered = [o for o in filtered if o.owner_id == owner_id]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = [o.to_dict() for o in filtered[start:end]]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message=""
        )

    def get_opportunity(self, tenant_id: int, opp_id: int) -> ApiResponse:
        """Get opportunity by ID"""
        opp = self._opportunities.get(opp_id)
        if not opp or opp.tenant_id != tenant_id:
            return ApiResponse.error(message="商机不存在", code=3001)
        return ApiResponse.success(data=opp.to_dict(), message="")

    def update_opportunity(self, tenant_id: int, opp_id: int, data: dict) -> ApiResponse:
        """Update opportunity fields"""
        opp = self._opportunities.get(opp_id)
        if not opp or opp.tenant_id != tenant_id:
            return ApiResponse.error(message="商机不存在", code=3001)

        for key in ['name', 'customer_id', 'pipeline_id', 'amount', 'probability', 'owner_id']:
            if key in data:
                setattr(opp, key, data[key])

        if 'stage' in data:
            opp.stage = Stage(data['stage']) if isinstance(data['stage'], str) else data['stage']
        if 'expected_close_date' in data:
            opp.expected_close_date = datetime.fromisoformat(data['expected_close_date'])

        opp.updated_at = datetime.utcnow()
        return ApiResponse.success(data=opp.to_dict(), message="商机更新成功")

    def change_stage(self, tenant_id: int, opp_id: int, stage: str) -> ApiResponse:
        """Change opportunity stage"""
        opp = self._opportunities.get(opp_id)
        if not opp or opp.tenant_id != tenant_id:
            return ApiResponse.error(message="商机不存在", code=3001)
        opp.stage = Stage(stage)
        opp.updated_at = datetime.utcnow()
        return ApiResponse.success(data={"id": opp_id, "stage": stage}, message="阶段更新成功")

    def get_forecast(self, tenant_id: int, owner_id: int = None) -> ApiResponse:
        """Get sales forecast by owner"""
        pipeline_ids = [p.id for p in self._pipelines.values() if p.tenant_id == tenant_id]

        pipeline_forecasts = {}
        for pid in pipeline_ids:
            pipeline_opps = [o for o in self._opportunities.values() if o.pipeline_id == pid and o.tenant_id == tenant_id]
            total_amount = sum(o.amount for o in pipeline_opps if o.stage not in [Stage.CLOSED_WON, Stage.CLOSED_LOST])
            pipeline_forecasts[pid] = float(total_amount)

        return ApiResponse.success(
            data={"owner_id": owner_id, "forecast": pipeline_forecasts},
            message=""
        )