"""Typed settings for stats-service, loaded from environment / .env."""

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

    # ─── Stats defaults ───
    stats_default_days: int = Field(default=30, ge=1, le=365)
    top_links_limit: int = Field(default=10, ge=1, le=100)

    # Shared secret required for destructive endpoints (clicks deletion).
    internal_api_token: str = "change_me_internal_token"

    # Path prefix for Swagger docs when served behind the gateway
    # (e.g. /api/stats → docs at /api/stats/docs). Empty = root.
    docs_prefix: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
