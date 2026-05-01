"""Standardized API response envelopes — requirement 7."""
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Single-item response envelope.

    Response shape:
        { "success": true, "message": "OK", "data": { ... } }
    """

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None

    @classmethod
    def ok(cls, data: T, message: str = "OK") -> "APIResponse[T]":
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str) -> "APIResponse[None]":
        return cls(success=False, message=message, data=None)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response envelope.

    Response shape:
        {
          "success": true,
          "data": [ ... items ... ],
          "total": 100,
          "page": 1,
          "page_size": 20,
          "total_pages": 5
        }
    """

    success: bool = True
    data: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0

    @classmethod
    def make(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        total_pages = (total + page_size - 1) // page_size
        return cls(
            success=True,
            data=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )