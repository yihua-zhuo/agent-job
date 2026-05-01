"""FastAPI application entry point — async-first, structured logging, centralized errors."""
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from configs.settings import settings
from middleware.logging import LoggingMiddleware, logger
from pkg.errors.app_exceptions import AppException

from api import customers_router, sales_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle — keep async engine warm."""
    from db.connection import ensure_engine

    ensure_engine()
    logger.info("app_started", env=settings.env, app_name=settings.app_name)
    yield
    from db.connection import dispose_engine

    dispose_engine()
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    # Determine OpenAPI availability based on environment
    docs_url = "/docs" if settings.openapi_enabled else None
    redoc_url = "/redoc" if settings.openapi_enabled else None
    openapi_url = "/openapi.json" if settings.openapi_enabled else None

    app = FastAPI(
        title=settings.app_name,
        description="CRM API — customers, pipelines, opportunities",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # JWT config stored on app state for dependency access
    app.state.jwt_secret = settings.jwt_secret
    app.state.jwt_algorithm = settings.jwt_algorithm

    # ── Middleware ──────────────────────────────────────────────────────────
    app.add_middleware(LoggingMiddleware)

    # CORS
    allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handlers ─────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.error("app_exception", code=exc.code, detail=exc.detail, path=request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", type=type(exc).__name__, detail=str(exc))
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "detail": "Internal server error"},
        )

    # ── Routes ─────────────────────────────────────────────────────────────
    app.include_router(customers_router)
    app.include_router(sales_router)

    @app.get("/")
    async def health():
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()