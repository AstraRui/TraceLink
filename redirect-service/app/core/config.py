"""Typed application settings, loaded from environment variables / .env.

Nothing secret is hard-coded here: every sensitive value comes from the
environment via pydantic-settings. The defaults are safe placeholders for
local development only.
"""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── PostgreSQL ───
    postgres_user: str = "shortener"
    postgres_password: str = "postgres"
    postgres_db: str = "shortener"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # ─── Redis (hot-link cache) ───
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    cache_ttl_seconds: int = 3600

    # ─── Short-code generation ───
    short_code_length: int = Field(default=7, ge=6, le=8)
    default_link_ttl_days: int = 0  # 0 = no expiry

    # ─── URLs ───
    base_url: str = "http://localhost:8080"
    stats_service_url: str = "http://stats-service:8000"

    # Shared secret required on link-management endpoints (set by admin panel).
    internal_api_token: str = "change_me_internal_token"

    # Path prefix for Swagger docs when served behind the gateway
    # (e.g. /api/redirect → docs at /api/redirect/docs). Empty = root.
    docs_prefix: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
