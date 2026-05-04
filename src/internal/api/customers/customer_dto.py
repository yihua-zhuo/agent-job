"""客户 DTO 定义"""
from dataclasses import dataclass


@dataclass
class CreateCustomerDTO:
    """创建客户 DTO"""
    name: str
    email: str
    phone: str | None = None
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class UpdateCustomerDTO:
    """更新客户 DTO"""
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    tags: list[str] | None = None
    status: str | None = None


@dataclass
class CustomerResponseDTO:
    """客户响应 DTO"""
    id: int
    name: str
    email: str
    status: str
    phone: str | None = None
    tags: list[str] = None
    created_at: str | None = None
    updated_at: str | None = None

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
