"""
API 响应模型
"""
from dataclasses import dataclass, field
from typing import Any, Optional, List, Generic, TypeVar
from datetime import datetime
from enum import Enum
import json


T = TypeVar('T')


class ResponseStatus(Enum):
    """响应状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    SERVER_ERROR = "server_error"


class ErrorCode(Enum):
    """错误码枚举"""
    # 通用错误 (1000-1999)
    UNKNOWN_ERROR = 1000
    INVALID_PARAMS = 1001
    MISSING_PARAMS = 1002
    UNAUTHORIZED_ACCESS = 1401
    FORBIDDEN_ACCESS = 1403
    NOT_FOUND = 1404
    INTERNAL_ERROR = 1500
    
    # 用户错误 (2000-2999)
    USER_NOT_FOUND = 2001
    USER_ALREADY_EXISTS = 2002
    INVALID_PASSWORD = 2003
    WEAK_PASSWORD = 2004
    EMAIL_ALREADY_EXISTS = 2005
    USERNAME_ALREADY_EXISTS = 2006
    ACCOUNT_DISABLED = 2007
    ACCOUNT_BANNED = 2008
    EMAIL_NOT_VERIFIED = 2009
    SESSION_EXPIRED = 2010
    
    # 资源错误 (3000-3999)
    RESOURCE_NOT_FOUND = 3001
    RESOURCE_ALREADY_EXISTS = 3002
    RESOURCE_LIMIT_EXCEEDED = 3003
    FILE_TOO_LARGE = 3004
    INVALID_FILE_TYPE = 3005


@dataclass
class ApiError:
    """API错误详情"""
    code: int
    message: str
    field: Optional[str] = None
    details: Optional[dict] = None


@dataclass
class PaginatedData(Generic[T]):
    """分页数据"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        return self.page > 1


@dataclass
class ApiResponse(Generic[T]):
    """通用API响应"""
    status: ResponseStatus
    message: str = ""
    data: Optional[T] = None
    errors: List[ApiError] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: Optional[str] = None
    
    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "操作成功", **kwargs) -> "ApiResponse[T]":
        """创建成功响应"""
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data=data,
            **{k: v for k, v in kwargs.items() if k not in ["status", "message", "data", "errors", "meta", "timestamp", "request_id"]}
        )
    
    @classmethod
    def error(cls, message: str, code: int = 1000, errors: List[ApiError] = None, **kwargs) -> "ApiResponse":
        """创建错误响应"""
        status_map = {
            1401: ResponseStatus.UNAUTHORIZED,
            1403: ResponseStatus.FORBIDDEN,
            1404: ResponseStatus.NOT_FOUND,
            1001: ResponseStatus.VALIDATION_ERROR,
            1500: ResponseStatus.SERVER_ERROR,
        }
        return cls(
            status=status_map.get(code, ResponseStatus.ERROR),
            message=message,
            errors=errors or [],
            **{k: v for k, v in kwargs.items() if k not in ["status", "message", "data", "errors", "meta", "timestamp", "request_id"]}
        )
    
    @classmethod
    def paginated(cls, items: List[T], total: int, page: int, page_size: int, message: str = "查询成功") -> "ApiResponse[PaginatedData[T]]":
        """创建分页响应"""
        total_pages = (total + page_size - 1) // page_size
        paginated_data = PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data=paginated_data,
            meta={"total": total, "page": page, "page_size": page_size}
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp
        }
        if self.data is not None:
            if hasattr(self.data, 'to_dict'):
                result["data"] = self.data.to_dict()
            else:
                result["data"] = self.data
        if self.errors:
            result["errors"] = [
                {"code": e.code, "message": e.message, "field": e.field}
                for e in self.errors
            ]
        if self.meta:
            result["meta"] = self.meta
        if self.request_id:
            result["request_id"] = self.request_id
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def __bool__(self) -> bool:
        """判断响应是否成功"""
        return self.status == ResponseStatus.SUCCESS
