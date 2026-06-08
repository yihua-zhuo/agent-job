"""Global FastAPI exception handlers.

Kept lightweight (no app factory imports) so unit tests can apply the same
JSON envelopes without pulling in the full application stack.
"""

import re
import uuid
import weakref

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from middleware.logging import logger
from pkg.errors.app_exceptions import AppException, ConflictException


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render HTTPException (and its FastAPI subclass) with the project envelope.

    Without this, a 404 or 405 would still flow through Starlette's default
    handler, but the body wouldn't match the project JSON shape. Re-raising
    inside the generic ``Exception`` handler isn't enough either — FastAPI
    dispatches by MRO, and we want the response to use the same
    ``success``/``request_id`` envelope as every other error.

    Structured ``exc.detail`` payloads (lists/dicts raised by routers and
    middleware) are preserved and returned as a ``detail`` field alongside
    a generic ``message`` so clients can still rely on ``message`` always
    being a string. String details are passed through directly as
    ``message`` (the common case for ``HTTPException(status_code=404,
    detail="Resource not found")``).
    """
    request_id = _resolve_request_id(request)
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
        extra: dict = {}
    else:
        message = "HTTP error"
        extra = {"detail": jsonable_encoder(detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": message,
            "request_id": request_id,
            **extra,
        },
        headers=getattr(exc, "headers", None),
    )


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
    layer (e.g. UNIQUE or FK violations from raw SQL). The ``get_db()``
    dependency already rolls back the session in its ``except`` branch
    before re-raising into this handler, so no additional rollback is
    needed here.
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

    AppException is registered separately and dispatched first by FastAPI
    based on the MRO. StarletteHTTPException is also handled by a
    dedicated handler (registered above the bare ``Exception`` handler)
    and dispatched by MRO before this catch-all runs, so this handler
    only ever sees non-HTTPException errors.

    For everything else we log the exception class name plus a sanitised
    message string and request_id to give operators enough diagnostic
    context to triage production failures without leaking sensitive
    details (e.g. connection strings, query parameters). The full
    traceback is emitted via ``exc_info=True`` on a separate log line
    below.
    """
    request_id = _resolve_request_id(request)
    message = _sanitise_message(str(exc))
    logger.error(
        "unhandled_exception",
        type=type(exc).__name__,
        message=message,
        path=request.url.path,
        request_id=request_id,
    )
    logger.error("unhandled_exception_traceback", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )


# Pattern to detect hex-encoded API keys or secrets (32+ hex characters
# in a row). Catches things like long random tokens that don't start with
# a known prefix.
_HEX_SECRET_RE = re.compile(r"\b[0-9a-f]{32,}\b", re.IGNORECASE)


def _sanitise_message(message: str) -> str:
    """Strip obvious secret-bearing substrings from exception messages.

    A defence-in-depth pass so that ``str(exc)`` (which may include
    parts of a connection string or query parameters) does not end up
    in structured logs verbatim. The full traceback at WARNING/ERROR
    is still emitted via ``exc_info=True``; this only controls the
    structured fields.
    """
    lower = message.lower()
    for marker in (
        "password=",
        "passwd=",
        "://",
        "secret=",
        "token=",
        "api_key=",
        "bearer ",
        # JWTs start with "eyJ" (base64-encoded JSON header)
        "eyj",
    ):
        if marker in lower:
            return "[message redacted — contains secret-like content]"
    if _HEX_SECRET_RE.search(message):
        return "[message redacted — contains secret-like content]"
    return message


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
# app instance. WeakSet holds app references so we don't pin them in memory
# after the test/app goes out of scope, and uses object identity (not `id()`)
# so a recycled id from a freed object can't accidentally mask a fresh app.
_REGISTERED_APPS: weakref.WeakSet[FastAPI] = weakref.WeakSet()


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global exception handlers on the given FastAPI app.

    Idempotent: a second call against the same app instance is a no-op.
    """
    if app in _REGISTERED_APPS:
        return
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    _REGISTERED_APPS.add(app)
