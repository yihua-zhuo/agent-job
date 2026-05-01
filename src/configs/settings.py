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
    secret_key: str = Field(default="dev-secret")
    jwt_secret: str = Field(default="dev-jwt-secret")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)

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