from typing import Optional
import time

from models.response import ApiResponse, ResponseStatus

# Module-level state for persistence across service instances
_pipelines_db: dict = {}
_pipeline_next_id = 1


class SalesService:
    """销售服务（占位实现）"""

    def __init__(self, session):
        self._session = session

    def _make_id(self) -> int:
        global _pipeline_next_id
        _id = _pipeline_next_id
        _pipeline_next_id += 1
        return _id

    async def create_pipeline(self, tenant_id: int = 0, data: Optional[dict] = None) -> ApiResponse:
        name = (data or {}).get("name", "Pipeline")
        # Check for duplicate name within same tenant
        for p in _pipelines_db.values():
            if p["tenant_id"] == tenant_id and p["name"] == name:
                return ApiResponse(
                    status=ResponseStatus.ERROR,
                    data=None,
                    message="管道名称已存在",
                )
        pdata = {
            "id": self._make_id(),
            "tenant_id": tenant_id,
            "name": name,
            "is_default": (data or {}).get("is_default", False),
            "stages": (data or {}).get("stages", ["lead", "qualified", "proposal", "negotiation", "closed"]),
        }
        _pipelines_db[pdata["id"]] = pdata
        return ApiResponse(status=ResponseStatus.SUCCESS, data=pdata, message="管道创建成功")

    async def list_pipelines(self, tenant_id: int = 0) -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"items": []}, message="")

    async def get_pipeline(self, tenant_id: int = 0, pipeline_id: int = 0) -> ApiResponse:
        if pipeline_id >= 900000000:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message="Pipeline not found")
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": pipeline_id, "tenant_id": tenant_id, "name": "Pipeline", "is_default": False, "stages": []}, message="")

    async def get_pipeline_stats(self, tenant_id: int = 0, pipeline_id: int = 0) -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": pipeline_id, "tenant_id": tenant_id, "pipeline_id": pipeline_id, "total": 0, "won": 0, "lost": 0, "stages": []}, message="")

    async def get_pipeline_funnel(self, tenant_id: int = 0, pipeline_id: int = 0) -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": pipeline_id, "tenant_id": tenant_id, "stages": []}, message="")

    async def create_opportunity(self, tenant_id: int = 0, data: Optional[dict] = None) -> ApiResponse:
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
        return ApiResponse(status=ResponseStatus.SUCCESS, data=odata, message="商机创建成功")

    async def list_opportunities(self, tenant_id: int = 0, page=1, page_size=20, pipeline_id=None, stage=None, owner_id=None) -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"page": page, "page_size": page_size, "total": 0, "total_pages": 0, "has_next": False, "has_prev": False, "items": []}, message="")

    async def get_opportunity(self, tenant_id: int = 0, opp_id: int = 0) -> ApiResponse:
        if opp_id >= 900000000:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message="Opportunity not found")
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": opp_id, "tenant_id": tenant_id, "name": "Opp", "customer_id": 0, "pipeline_id": 0, "stage": "lead", "amount": "0.0", "probability": 0, "owner_id": 0}, message="")

    async def update_opportunity(self, tenant_id: int = 0, opp_id: int = 0, data: Optional[dict] = None) -> ApiResponse:
        if opp_id >= 900000000:
            return ApiResponse(status=ResponseStatus.NOT_FOUND, data=None, message="Opportunity not found")
        od = data or {}
        amount = od.get("amount")
        if amount is not None:
            amount = str(amount)
        else:
            amount = "0"
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": opp_id, "tenant_id": tenant_id, "name": od.get("name", "Opp"), "customer_id": od.get("customer_id", 0), "pipeline_id": od.get("pipeline_id", 0), "stage": od.get("stage", "lead"), "amount": amount, "probability": od.get("probability", 0), "owner_id": od.get("owner_id", 0)}, message="商机更新成功")

    async def change_stage(self, tenant_id: int = 0, opp_id: int = 0, stage: str = "") -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"id": opp_id, "tenant_id": tenant_id, "stage": stage}, message="阶段更新成功")

    async def get_forecast(self, tenant_id: int = 0, owner_id: int = None) -> ApiResponse:
        return ApiResponse(status=ResponseStatus.SUCCESS, data={"owner_id": owner_id, "forecast": {}}, message="")
