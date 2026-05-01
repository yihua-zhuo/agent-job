"""FastAPI application entry point - replaces Flask with full async support."""
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routes after creating app to avoid circular imports
from src.api.routes import customers_router, sales_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events. Keep engine warm for asyncpg connections."""
    from db.connection import ensure_engine
    ensure_engine()
    yield
    # Shutdown: dispose engine pool
    from db.connection import dispose_engine
    dispose_engine()


def create_app() -> FastAPI:
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("SECRET_KEY environment variable is required in production")
        secret_key = secrets.token_hex(32)

    jwt_secret = os.environ.get('JWT_SECRET') or os.environ.get('JWT_SECRET_KEY') or secret_key
    jwt_algorithm = 'HS256'

    app = FastAPI(
        title='agent-job',
        docs_url='/docs' if os.environ.get('FLASK_ENV') != 'production' else None,
        redoc_url='/redoc' if os.environ.get('FLASK_ENV') != 'production' else None,
    )

    # JWT config available to dependency
    app.state.jwt_secret = jwt_secret
    app.state.jwt_algorithm = jwt_algorithm

    # CORS - same logic as original Flask
    cors_origins = os.environ.get('CORS_ORIGINS')
    if not cors_origins:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("CORS_ORIGINS environment variable is required in production")
        cors_origins = 'localhost'
    allowed = [o.strip() for o in cors_origins.split(',') if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all API routes
    app.include_router(customers_router)
    app.include_router(sales_router)

    @app.get('/')
    async def health():
        return {'status': 'ok', 'service': 'agent-job'}

    return app


app = create_app()