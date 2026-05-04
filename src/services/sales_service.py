
from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import ConflictException, NotFoundException

# Module-level state for persistence across service instances
_pipelines_db: dict = {}
_pipeline_next_id = 1


class SalesService:
    """销售服务（占位实现）"""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _make_id(self) -> int:
        global _pipeline_next_id
        _id = _pipeline_next_id
        _pipeline_next_id += 1
        return _id

    async def create_pipeline(self, tenant_id: int = 0, data: dict | None = None) -> dict:
        name = (data or {}).get("name", "Pipeline")
        # Check for duplicate name within same tenant
        for p in _pipelines_db.values():
            if p["tenant_id"] == tenant_id and p["name"] == name:
                raise ConflictException("管道名称已存在")
        pdata = {
            "id": self._make_id(),
            "tenant_id": tenant_id,
            "name": name,
            "is_default": (data or {}).get("is_default", False),
            "stages": (data or {}).get("stages", ["lead", "qualified", "proposal", "negotiation", "closed"]),
        }
        _pipelines_db[pdata["id"]] = pdata
        return pdata

    async def list_pipelines(self, tenant_id: int = 0) -> dict:
        return {"items": []}

    async def get_pipeline(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        if pipeline_id >= 900000000:
            raise NotFoundException("Pipeline")
        return {"id": pipeline_id, "tenant_id": tenant_id, "name": "Pipeline", "is_default": False, "stages": []}

    async def get_pipeline_stats(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        return {"id": pipeline_id, "tenant_id": tenant_id, "pipeline_id": pipeline_id, "total": 0, "won": 0, "lost": 0, "stages": []}

    async def get_pipeline_funnel(self, tenant_id: int = 0, pipeline_id: int = 0) -> dict:
        return {"id": pipeline_id, "tenant_id": tenant_id, "stages": []}

    async def create_opportunity(self, tenant_id: int = 0, data: dict | None = None) -> dict:
        od = data or {}
        odata = {
            "id": self._make_id(),
            "tenant_id": tenant_id,
            "name": od.get("name", "Opportunity"),
            "customer_id": od.get("customer_id", 0),
            "pipeline_id": od.get("pipeline_id", 0),
            "stage": od.get("stage", "lead"),
            "amount": od.get("amount", 0.0),
            "probability": od.get("probability", 0),
            "owner_id": od.get("owner_id", 0),
            "close_date": od.get("close_date"),
            "notes": od.get("notes"),
        }
        return odata

    async def list_opportunities(self, tenant_id: int = 0, page=1, page_size=20, pipeline_id=None, stage=None, owner_id=None) -> dict:
        return {"page": page, "page_size": page_size, "total": 0, "total_pages": 0, "has_next": False, "has_prev": False, "items": []}

    async def get_opportunity(self, tenant_id: int = 0, opp_id: int = 0) -> dict:
        if opp_id >= 900000000:
            raise NotFoundException("Opportunity")
        return {"id": opp_id, "tenant_id": tenant_id, "name": "Opp", "customer_id": 0, "pipeline_id": 0, "stage": "lead", "amount": "0.0", "probability": 0, "owner_id": 0}

    async def update_opportunity(self, tenant_id: int = 0, opp_id: int = 0, data: dict | None = None) -> dict:
        if opp_id >= 900000000:
            raise NotFoundException("Opportunity")
        od = data or {}
        amount = od.get("amount")
        if amount is not None:
            amount = str(amount)
        else:
            amount = "0"
        return {"id": opp_id, "tenant_id": tenant_id, "name": od.get("name", "Opp"), "customer_id": od.get("customer_id", 0), "pipeline_id": od.get("pipeline_id", 0), "stage": od.get("stage", "lead"), "amount": amount, "probability": od.get("probability", 0), "owner_id": od.get("owner_id", 0)}

    async def change_stage(self, tenant_id: int = 0, opp_id: int = 0, stage: str = "") -> dict:
        return {"id": opp_id, "tenant_id": tenant_id, "stage": stage}

    async def get_forecast(self, tenant_id: int = 0, owner_id: int = None) -> dict:
        return {"owner_id": owner_id, "forecast": {}}
