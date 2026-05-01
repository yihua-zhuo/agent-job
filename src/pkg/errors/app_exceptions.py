"""Centralized application exceptions — no raw HTTPException raises in services."""
from fastapi import HTTPException


class AppException(Exception):
    """Base application exception with structured fields.

    Subclasses set status_code, detail, and an application-level code.
    The global exception handler in main.py translates these to JSON responses.
    """

    def __init__(self, status_code: int, detail: str, code: str):
        self.status_code = status_code
        self.detail = detail
        self.code = code
        super().__init__(detail)

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail}


class NotFoundException(AppException):
    """404 for a missing resource."""

    def __init__(self, resource: str):
        super().__init__(404, f"{resource} not found", "NOT_FOUND")


class ConflictException(AppException):
    """409 for duplicate / constraint violations."""

    def __init__(self, detail: str):
        super().__init__(409, detail, "CONFLICT")


class ValidationException(AppException):
    """422 for request validation failures (not HTTP 422, business logic)."""

    def __init__(self, detail: str):
        super().__init__(422, detail, "VALIDATION_ERROR")


class UnauthorizedException(AppException):
    """401 for missing/invalid auth."""

    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(401, detail, "UNAUTHORIZED")


class ForbiddenException(AppException):
    """403 for insufficient permissions."""

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(403, detail, "FORBIDDEN")


class InternalServerException(AppException):
    """500 for unexpected errors."""

    def __init__(self, detail: str = "Internal server error"):
        super().__init__(500, detail, "INTERNAL_ERROR")