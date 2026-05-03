from dataclasses import dataclass
from typing import Optional


@dataclass
class ApiResponse:
    """简单API响应对象"""
    success: bool = True
    data: Optional[dict] = None
    message: str = ""

    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'message': self.message
        }


class SalesService:
    """销售服务（占位实现）"""

    def create_pipeline(self, data: dict) -> ApiResponse:
        return ApiResponse(success=True, data=data, message="管道创建成功")

    def list_pipelines(self) -> ApiResponse:
        return ApiResponse(success=True, data={"items": []}, message="")

    def get_pipeline(self, pipeline_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"id": pipeline_id}, message="")

    def get_pipeline_stats(self, pipeline_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"pipeline_id": pipeline_id, "total": 0, "won": 0, "lost": 0}, message="")

    def get_pipeline_funnel(self, pipeline_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"pipeline_id": pipeline_id, "stages": []}, message="")

    def create_opportunity(self, data: dict) -> ApiResponse:
        return ApiResponse(success=True, data=data, message="商机创建成功")

    def list_opportunities(self, page=1, page_size=20, pipeline_id=None, stage=None, owner_id=None) -> ApiResponse:
        return ApiResponse(success=True, data={"page": page, "page_size": page_size, "items": []}, message="")

    def get_opportunity(self, opp_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"id": opp_id}, message="")

    def update_opportunity(self, opp_id: int, data: dict) -> ApiResponse:
        return ApiResponse(success=True, data={"id": opp_id, **data}, message="商机更新成功")

    def change_stage(self, opp_id: int, stage: str) -> ApiResponse:
        return ApiResponse(success=True, data={"id": opp_id, "stage": stage}, message="阶段更新成功")

    def get_forecast(self, owner_id: int = None) -> ApiResponse:
        return ApiResponse(success=True, data={"owner_id": owner_id, "forecast": 0}, message="")
