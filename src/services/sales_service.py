"""Sales service — pipeline and opportunity CRUD via SQLAlchemy ORM.

Returns dicts (not ORM objects) because routers and existing tests rely on
the dict shape with stages embedded.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.opportunity import OpportunityModel
from db.models.pipeline import PipelineModel
from db.models.pipeline_stage import PipelineStageModel
from pkg.errors.app_exceptions import ConflictException, NotFoundException, ValidationException

DEFAULT_STAGES = ["lead", "qualified", "proposal", "negotiation", "closed"]


def _opp_to_dict(o: OpportunityModel) -> dict:
    d = o.to_dict()
    d["amount"] = float(o.amount) if o.amount is not None else 0.0
    d["close_date"] = d.get("expected_close_date")
    return d


def _coerce_amount(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


class SalesService:
    """Sales / opportunity management backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Pipelines
    # -------------------------------------------------------------------------

    async def _get_pipeline_stages(self, pipeline_id: int, tenant_id: int) -> list[str]:
        stages_result = await self.session.execute(
            select(PipelineStageModel.name)
            .join(PipelineModel, PipelineStageModel.pipeline_id == PipelineModel.id)
            .where(PipelineStageModel.pipeline_id == pipeline_id)
            .where(PipelineModel.tenant_id == tenant_id)
            .order_by(PipelineStageModel.display_order)
        )
        return [name for (name,) in stages_result.all()]

    async def _pipeline_to_dict(self, pipeline: PipelineModel) -> dict:
        return {
            "id": pipeline.id,
            "tenant_id": pipeline.tenant_id,
            "name": pipeline.name,
            "is_default": pipeline.is_default,
            "stages": await self._get_pipeline_stages(pipeline.id, pipeline.tenant_id),
        }

    async def create_pipeline(self, tenant_id: int = 0, data: dict | None = None) -> dict:
        d = data or {}
        name = d.get("name", "Pipeline")

        existing = await self.session.execute(
            select(PipelineModel).where(and_(PipelineModel.tenant_id == tenant_id, PipelineModel.name == name))
        )
        if existing.scalar_one_or_none():
            raise ConflictException("管道名称已存在")

        now = datetime.now(UTC)
        pipeline = PipelineModel(
            tenant_id=tenant_id,
            name=name,
            is_default=d.get("is_default", False),
            created_at=now,
            updated_at=now,
        )
        self.session.add(pipeline)
        await self.session.flush()

        stage_names = d.get("stages") or DEFAULT_STAGES
        for idx, stage_name in enumerate(stage_names):
            self.session.add(
                PipelineStageModel(
                    pipeline_id=pipeline.id,
                    name=stage_name,
                    display_order=idx,
                    created_at=now,
                )
            )
        await self.session.flush()
        await self.session.flush()
        return await self._pipeline_to_dict(pipeline)

    async def list_pipelines(self, tenant_id: int = 0) -> dict:
        result = await self.session.execute(
            select(PipelineModel).where(PipelineModel.tenant_id == tenant_id).order_by(PipelineModel.id)
        )
        pipelines = result.scalars().all()
        items = [await self._pipeline_to_dict(p) for p in pipelines]
        return {"items": items}

    async def get_pipeline(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        result = await self.session.execute(
            select(PipelineModel).where(and_(PipelineModel.id == pipeline_id, PipelineModel.tenant_id == tenant_id))
        )
        pipeline = result.scalar_one_or_none()
        if pipeline is None:
            raise NotFoundException("Pipeline")
        return await self._pipeline_to_dict(pipeline)

    async def get_pipeline_stats(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        stage_names = await self._get_pipeline_stages(pipeline_id, tenant_id)
        result = await self.session.execute(
            select(
                OpportunityModel.stage,
                func.count(OpportunityModel.id),
                func.coalesce(func.sum(OpportunityModel.amount), 0),
            )
            .where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.pipeline_id == pipeline_id,
                )
            )
            .group_by(OpportunityModel.stage)
        )
        per_stage = {stage: {"count": count, "amount": float(amount)} for stage, count, amount in result.all()}

        total = sum(s["count"] for s in per_stage.values())
        won = per_stage.get("closed_won", per_stage.get("won", {"count": 0}))["count"]
        lost = per_stage.get("closed_lost", per_stage.get("lost", {"count": 0}))["count"]

        stages = [
            {
                "stage": name,
                "count": per_stage.get(name, {"count": 0})["count"],
                "amount": per_stage.get(name, {"amount": 0.0})["amount"],
            }
            for name in stage_names
        ]
        return {
            "id": pipeline_id,
            "tenant_id": tenant_id,
            "pipeline_id": pipeline_id,
            "total": total,
            "won": won,
            "lost": lost,
            "stages": stages,
        }

    async def get_pipeline_funnel(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        stage_names = await self._get_pipeline_stages(pipeline_id, tenant_id)
        result = await self.session.execute(
            select(OpportunityModel.stage, func.count(OpportunityModel.id))
            .where(
                and_(
                    OpportunityModel.tenant_id == tenant_id,
                    OpportunityModel.pipeline_id == pipeline_id,
                )
            )
            .group_by(OpportunityModel.stage)
        )
        counts = {stage: count for stage, count in result.all()}
        stages = [{"stage": name, "count": counts.get(name, 0)} for name in stage_names]
        return {"id": pipeline_id, "tenant_id": tenant_id, "stages": stages}

    # -------------------------------------------------------------------------
    # Opportunities
    # -------------------------------------------------------------------------

    async def create_opportunity(self, tenant_id: int = 0, data: dict | None = None) -> dict:
        d = data or {}
        now = datetime.now(UTC)
        close_date = d.get("expected_close_date") or d.get("close_date")
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=d.get("customer_id", 0),
            name=d.get("name", "Opportunity"),
            stage=d.get("stage", "lead"),
            amount=_coerce_amount(d.get("amount", 0)),
            probability=int(d.get("probability", 0) or 0),
            owner_id=d.get("owner_id", 0),
            pipeline_id=d.get("pipeline_id"),
            expected_close_date=close_date if isinstance(close_date, datetime) else None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(opp)
        await self.session.flush()
        await self.session.refresh(opp)
        return _opp_to_dict(opp)

    async def list_opportunities(
        self,
        tenant_id: int = 0,
        page: int = 1,
        page_size: int = 20,
        pipeline_id: int | None = None,
        stage: str | None = None,
        owner_id: int | None = None,
    ) -> dict:
        conditions = [OpportunityModel.tenant_id == tenant_id]
        if pipeline_id is not None:
            conditions.append(OpportunityModel.pipeline_id == pipeline_id)
        if stage is not None:
            conditions.append(OpportunityModel.stage == stage)
        if owner_id is not None:
            conditions.append(OpportunityModel.owner_id == owner_id)

        count_result = await self.session.execute(select(func.count(OpportunityModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(OpportunityModel)
            .where(and_(*conditions))
            .order_by(OpportunityModel.id)
            .offset(offset)
            .limit(page_size)
        )
        items = [_opp_to_dict(o) for o in result.scalars().all()]

        total_pages = (total + page_size - 1) // page_size if total else 0
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": offset + page_size < total,
            "has_prev": page > 1,
            "items": items,
        }

    async def _fetch_opportunity(self, tenant_id: int, opp_id: int) -> OpportunityModel:
        result = await self.session.execute(
            select(OpportunityModel).where(and_(OpportunityModel.id == opp_id, OpportunityModel.tenant_id == tenant_id))
        )
        opp = result.scalar_one_or_none()
        if opp is None:
            raise NotFoundException("Opportunity")
        return opp

    async def get_opportunity(self, tenant_id: int = 0, opp_id: int = 0) -> dict:
        return _opp_to_dict(await self._fetch_opportunity(tenant_id, opp_id))

    async def update_opportunity(
        self,
        tenant_id: int = 0,
        opp_id: int = 0,
        data: dict | None = None,
    ) -> dict:
        await self._fetch_opportunity(tenant_id, opp_id)
        d = data or {}

        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key in ("name", "stage", "probability", "owner_id", "pipeline_id", "customer_id"):
            if key in d:
                update_values[key] = d[key]
        if "amount" in d:
            update_values["amount"] = _coerce_amount(d["amount"])
        close_date = d.get("expected_close_date") or d.get("close_date")
        if close_date is not None and isinstance(close_date, datetime):
            update_values["expected_close_date"] = close_date

        await self.session.execute(
            update(OpportunityModel).where(OpportunityModel.id == opp_id).values(**update_values)
        )
        await self.session.flush()

        refreshed = await self._fetch_opportunity(tenant_id, opp_id)
        return _opp_to_dict(refreshed)

    async def change_stage(self, tenant_id: int = 0, opp_id: int = 0, stage: str = "") -> OpportunityModel:
        opportunity = await self._fetch_opportunity(tenant_id, opp_id)
        if opportunity.pipeline_id is not None:
            allowed_stages = await self._get_pipeline_stages(opportunity.pipeline_id, tenant_id)
            if stage not in allowed_stages:
                raise ValidationException("Stage is not defined in the opportunity pipeline")
        await self.session.execute(
            update(OpportunityModel)
            .where(and_(OpportunityModel.id == opp_id, OpportunityModel.tenant_id == tenant_id))
            .values(stage=stage, updated_at=datetime.now(UTC))
        )
        await self.session.flush()
        refreshed = await self._fetch_opportunity(tenant_id, opp_id)
        return refreshed

    async def get_forecast(self, tenant_id: int = 0, owner_id: int | None = None) -> dict:
        conditions = [OpportunityModel.tenant_id == tenant_id]
        if owner_id is not None:
            conditions.append(OpportunityModel.owner_id == owner_id)

        result = await self.session.execute(
            select(
                OpportunityModel.stage,
                func.count(OpportunityModel.id),
                func.coalesce(func.sum(OpportunityModel.amount), 0),
                func.coalesce(func.sum(OpportunityModel.amount * OpportunityModel.probability / 100), 0),
            )
            .where(and_(*conditions))
            .group_by(OpportunityModel.stage)
        )
        forecast: dict[str, dict] = {}
        for stage, count, amount, weighted in result.all():
            forecast[stage] = {
                "count": count,
                "amount": float(amount),
                "weighted_amount": float(weighted),
            }
        return {"owner_id": owner_id, "forecast": forecast}
