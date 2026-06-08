"""Global FastAPI exception handlers.

Kept lightweight (no app factory imports) so unit tests can apply the same
JSON envelopes without pulling in the full application stack.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from middleware.logging import logger
from pkg.errors.app_exceptions import AppException


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global exception handlers on the given FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Reshape HTTPException to ErrorEnvelope shape for Swagger consistency."""
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_exception",
            type=type(exc).__name__,
            detail=str(exc),
            request_id=request_id,
            path=request.url.path,
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
