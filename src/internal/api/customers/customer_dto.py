"""客户 DTO 定义"""
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class CreateCustomerDTO:
    """创建客户 DTO"""
    name: str
    email: str
    phone: Optional[str] = None
    tags: Optional[List[str]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class UpdateCustomerDTO:
    """更新客户 DTO"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


@dataclass
class CustomerResponseDTO:
    """客户响应 DTO"""
    id: int
    name: str
    email: str
    status: str
    phone: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "phone": self.phone,
            "tags": self.tags or [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
