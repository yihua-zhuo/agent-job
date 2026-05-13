"""Application configuration via pydantic-settings — no raw os.getenv() in business logic."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration loaded from .env via pydantic-settings."""

    app_name: str = Field(default="agent-job", description="Service name")
    env: str = Field(default="development", description="Environment: development | production")
    debug: bool = Field(default=False)

    # Database
    database_url: str = Field(
        description="Async DB connection string (postgresql+asyncpg://...)",
    )
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)

    # JWT
    secret_key: str | None = Field(default=None)
    jwt_secret: str | None = Field(default=None)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)

    # WebAuthn
    webauthn_rp_id: str | None = Field(default=None, description="WebAuthn Relying Party ID (e.g. localhost or your domain)")
    webauthn_rp_name: str | None = Field(default=None, description="WebAuthn Relying Party name")

    # CORS
    cors_origins: str = Field(default="localhost")

    # OpenAPI
    openapi_enabled: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
if settings.env not in {"development", "local", "test"} and (
    not settings.secret_key or not settings.jwt_secret
):
    raise RuntimeError("SECRET_KEY and JWT_SECRET are required outside local development")
