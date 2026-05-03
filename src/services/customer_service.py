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


class CustomerService:
    """客户服务（占位实现）"""

    def create_customer(self, data: dict) -> ApiResponse:
        return ApiResponse(success=True, data=data, message="客户创建成功")

    def list_customers(self, page=1, page_size=20, status=None, owner_id=None, tags=None) -> ApiResponse:
        return ApiResponse(success=True, data={"page": page, "page_size": page_size, "items": []}, message="")

    def get_customer(self, customer_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id}, message="")

    def update_customer(self, customer_id: int, data: dict) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id, **data}, message="客户更新成功")

    def delete_customer(self, customer_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id}, message="客户删除成功")

    def search_customers(self, keyword: str) -> ApiResponse:
        return ApiResponse(success=True, data={"keyword": keyword, "items": []}, message="")

    def add_tag(self, customer_id: int, tag: str) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id, "tag": tag}, message="标签添加成功")

    def remove_tag(self, customer_id: int, tag: str) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id, "tag": tag}, message="标签移除成功")

    def change_status(self, customer_id: int, status: str) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id, "status": status}, message="状态更新成功")

    def assign_owner(self, customer_id: int, owner_id: int) -> ApiResponse:
        return ApiResponse(success=True, data={"id": customer_id, "owner_id": owner_id}, message="负责人分配成功")

    def bulk_import(self, customers: list) -> ApiResponse:
        return ApiResponse(success=True, data={"imported": len(customers)}, message=f"成功导入{len(customers)}条客户记录")
