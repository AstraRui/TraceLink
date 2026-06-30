"""Test fixtures: in-memory sqlite + overridden cache/stats dependencies.

No real Postgres, Redis or stats-service is touched. The app is driven through
httpx's ASGI transport, so there is no live server either.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_session
from app.main import app
from app.models import link  # noqa: F401 -- register the model's table
from app.schemas.event import ClickEvent
from app.services.cache import get_cache
from app.services.events import get_click_emitter


class FakeCache:
    """In-memory stand-in for the Redis L1 cache."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get_url(self, code: str) -> str | None:
        return self.store.get(code)

    async def set_url(self, code: str, url: str, ttl: int | None = None) -> None:
        self.store[code] = url

    async def invalidate(self, code: str) -> None:
        self.store.pop(code, None)


@dataclass
class Ctx:
    client: AsyncClient
    cache: FakeCache
    events: list[ClickEvent]
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def api() -> AsyncIterator[Ctx]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    fake_cache = FakeCache()
    events: list[ClickEvent] = []

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def override_cache() -> FakeCache:
        return fake_cache

    async def record_event(event: ClickEvent, trace_id: str) -> None:
        events.append(event)

    def override_emitter() -> object:
        return record_event

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cache] = override_cache
    app.dependency_overrides[get_click_emitter] = override_emitter

    transport = ASGITransport(app=app)
    # Link-management endpoints require the internal token; send it by default.
    headers = {"X-Internal-Token": settings.internal_api_token}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield Ctx(client=client, cache=fake_cache, events=events, session_factory=session_factory)

    app.dependency_overrides.clear()
    await engine.dispose()
