"""Test fixtures: in-memory sqlite + fake downstream clients.

No real Postgres, redirect-service or stats-service is touched. The app is
driven through httpx's ASGI transport (no live server).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.routes import (
    get_health_checker,
    get_log_reader,
    get_redirect_client,
    get_stats_client,
)
from app.core.auth import get_current_user
from app.db.session import Base, get_session
from app.main import app
from app.models import user as _user_table  # noqa: F401 -- register the model's table
from app.models.user import User
from app.services.bootstrap import ensure_admin_user
from app.services.health import HealthComponent
from app.services.logs import LogRow


def _new_engine() -> Any:
    return create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = _new_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


class FakeRedirectClient:
    def __init__(self) -> None:
        self.links: list[dict[str, Any]] = []
        self.created: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.error: Exception | None = None

    async def delete_link(self, short_code: str) -> None:
        self.deleted.append(short_code)
        self.links = [link for link in self.links if link["short_code"] != short_code]

    async def list_links(self, owner_id: int) -> list[dict[str, Any]]:
        return list(self.links)

    async def create_link(
        self,
        *,
        original_url: str,
        owner_id: int,
        is_private: bool = False,
        ttl_days: int | None = None,
    ) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        link = {
            "id": len(self.links) + 1,
            "short_code": "abc1234",
            "short_url": "http://localhost:8080/abc1234",
            "original_url": original_url,
            "owner_id": owner_id,
            "is_private": is_private,
            "expires_at": None,
        }
        self.links.insert(0, link)
        self.created.append(
            {
                "original_url": original_url,
                "owner_id": owner_id,
                "is_private": is_private,
                "ttl_days": ttl_days,
            }
        )
        return link


class FakeStatsClient:
    def __init__(self) -> None:
        self.summary: dict[str, Any] = {
            "total_clicks": 0,
            "clicks_by_day": [],
            "top_links": [],
            "devices": [],
            "browsers": [],
            "operating_systems": [],
        }
        self.deleted: list[str] = []

    async def get_summary(
        self, short_code: str | None = None, days: int | None = None
    ) -> dict[str, Any]:
        return self.summary

    async def delete_clicks(self, short_code: str) -> None:
        self.deleted.append(short_code)


class FakeHealthChecker:
    def __init__(self) -> None:
        self.components: list[HealthComponent] = [
            HealthComponent("PostgreSQL", True),
            HealthComponent("Redis", True),
            HealthComponent("Redirect API", True),
            HealthComponent("Stats API", True),
        ]

    async def gather(self) -> list[HealthComponent]:
        return self.components


class FakeLogReader:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.rows: list[LogRow] = [
            LogRow(now, "admin", "INFO", "abc123def456ff", "admin.access", "ADMIN_HOME_RENDERED"),
            LogRow(now, "redirect", "ERROR", "abc123def456ff", "redirect.api", "boom failure"),
        ]

    async def fetch(
        self, service: str | None = None, level: str | None = None, limit: int = 200
    ) -> list[LogRow]:
        rows = self.rows
        if service:
            rows = [r for r in rows if r.service == service]
        if level:
            rows = [r for r in rows if r.level == level]
        return rows


@dataclass
class Ctx:
    client: AsyncClient
    redirect_client: FakeRedirectClient
    stats_client: FakeStatsClient
    health: FakeHealthChecker
    logs: FakeLogReader
    session_factory: async_sessionmaker[AsyncSession]

    def authenticate_as(self, user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user


@pytest_asyncio.fixture
async def api() -> AsyncIterator[Ctx]:
    engine = _new_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed the admin user so the real login flow can be exercised.
    async with session_factory() as db:
        await ensure_admin_user(db)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db:
            yield db

    fake_redirect = FakeRedirectClient()
    fake_stats = FakeStatsClient()
    fake_health = FakeHealthChecker()
    fake_logs = FakeLogReader()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redirect_client] = lambda: fake_redirect
    app.dependency_overrides[get_stats_client] = lambda: fake_stats
    app.dependency_overrides[get_health_checker] = lambda: fake_health
    app.dependency_overrides[get_log_reader] = lambda: fake_logs

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield Ctx(
            client=client,
            redirect_client=fake_redirect,
            stats_client=fake_stats,
            health=fake_health,
            logs=fake_logs,
            session_factory=session_factory,
        )

    app.dependency_overrides.clear()
    await engine.dispose()
