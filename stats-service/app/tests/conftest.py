"""Test fixtures: in-memory sqlite session + ASGI client.

No real Postgres is touched; the app is driven through httpx's ASGI transport.
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
from app.models import click  # noqa: F401 -- register the model's table


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


@dataclass
class Ctx:
    client: AsyncClient
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

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db:
            yield db

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    # Destructive endpoints require the internal token; send it by default.
    headers = {"X-Internal-Token": settings.internal_api_token}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield Ctx(client=client, session_factory=session_factory)

    app.dependency_overrides.clear()
    await engine.dispose()
