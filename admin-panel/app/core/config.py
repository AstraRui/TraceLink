"""Typed settings for admin-panel, loaded from environment / .env."""

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

    # ─── Redis (used only for the System Health probe) ───
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # ─── JWT / session cookie ───
    jwt_secret: str = "change_me_jwt_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=1)
    cookie_name: str = "access_token"
    cookie_secure: bool = False  # set True when served over HTTPS

    # ─── External services (internal docker network) ───
    redirect_service_url: str = "http://redirect-service:8000"
    stats_service_url: str = "http://stats-service:8000"
    # Shared secret the admin presents to redirect-service for write calls.
    internal_api_token: str = "change_me_internal_token"

    # ─── Public base URL (for short links / QR codes) ───
    base_url: str = "http://localhost:8080"

    # ─── First admin user (bootstrapped on startup) ───
    admin_username: str = "admin"
    admin_password: str = "change_me_admin"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

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
