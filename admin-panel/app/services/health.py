"""System-health probes for the dashboard panel.

Each dependency is checked independently and concurrently; every check is
defensive (failures become a red "down" indicator, never an exception).
"""

import asyncio
from dataclasses import dataclass

import httpx
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_TIMEOUT_SECONDS = 2.0


@dataclass
class HealthComponent:
    name: str
    ok: bool


class HealthChecker:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _check_postgres(self) -> bool:
        try:
            await self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _check_redis(self) -> bool:
        client: redis.Redis = redis.from_url(settings.redis_url)
        try:
            return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()

    async def _check_http(self, base_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{base_url}/health")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def gather(self) -> list[HealthComponent]:
        postgres, redis_ok, redirect_ok, stats_ok = await asyncio.gather(
            self._check_postgres(),
            self._check_redis(),
            self._check_http(settings.redirect_service_url),
            self._check_http(settings.stats_service_url),
        )
        return [
            HealthComponent("PostgreSQL", postgres),
            HealthComponent("Redis", redis_ok),
            HealthComponent("Redirect API", redirect_ok),
            HealthComponent("Stats API", stats_ok),
        ]
