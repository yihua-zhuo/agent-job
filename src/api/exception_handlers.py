"""Global FastAPI exception handlers.

Kept lightweight (no app factory imports) so unit tests can apply the same
JSON envelopes without pulling in the full application stack.
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from middleware.logging import logger
from pkg.errors.app_exceptions import AppException, ConflictException


# ── Module-level handler references (named functions keep FastAPI's
# exception-handler registry consistent across re-registration).
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Translate AppException subclasses to the project JSON envelope."""
    request_id = _resolve_request_id(request)
    logger.error(
        "app_exception",
        code=exc.code,
        detail=exc.detail,
        path=request.url.path,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "code": exc.code,
            "request_id": request_id,
        },
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Translate SQLAlchemy IntegrityError to a 409 ConflictException envelope.

    Services should raise ConflictException explicitly when possible; this
    handler catches DB-level integrity errors that escape past the service
    layer (e.g. UNIQUE or FK violations from raw SQL).
    """
    request_id = _resolve_request_id(request)
    logger.error(
        "integrity_error",
        type=type(exc).__name__,
        path=request.url.path,
        request_id=request_id,
    )
    conflict = ConflictException("Database integrity constraint violated")
    return JSONResponse(
        status_code=conflict.status_code,
        content={
            "success": False,
            "message": conflict.detail,
            "code": conflict.code,
            "request_id": request_id,
        },
    )


async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return structured 422 with field details for Pydantic validation errors.

    Replaces FastAPI's default 422 envelope with the project JSON shape so
    clients see the same `success` / `code` / `request_id` fields as for
    every other error.
    """
    request_id = _resolve_request_id(request)
    # jsonable_encoder strips non-serializable values (e.g. raw ValueError
    # objects in Pydantic's `ctx` field) so the response can be rendered.
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request validation failed",
            "code": "VALIDATION_ERROR",
            "request_id": request_id,
            "errors": jsonable_encoder(exc.errors()),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any unhandled exception.

    Only non-AppException exceptions reach here because AppException is
    registered first and FastAPI dispatches by MRO. We log only the
    exception class name and request_id to avoid leaking sensitive
    details (connection strings, query parameters) into logs.
    """
    request_id = _resolve_request_id(request)
    logger.error(
        "unhandled_exception",
        type=type(exc).__name__,
        path=request.url.path,
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )


def _resolve_request_id(request: Request) -> str:
    """Return the request_id from middleware state, or generate one.

    request_id is always set by the request-id middleware; this is a
    defence-in-depth fallback for requests that bypass the middleware
    (e.g. internal health-check calls).
    """
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
    return request_id


# ── Idempotent registration ───────────────────────────────────────────────
# Module-level handler references let callers re-register safely without
# FastAPI's exception-handler dict accumulating duplicates for a second
# app instance.
_REGISTERED_APPS: set[int] = set()


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global exception handlers on the given FastAPI app.

    Idempotent: a second call against the same app instance is a no-op.
    """
    if id(app) in _REGISTERED_APPS:
        return
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    _REGISTERED_APPS.add(id(app))
