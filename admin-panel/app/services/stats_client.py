"""HTTP client for talking to stats-service (read-only, internal network)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import trace_id_var

_TIMEOUT_SECONDS = 5.0


async def _inject_trace(request: httpx.Request) -> None:
    request.headers["X-Request-ID"] = trace_id_var.get()


class StatsClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def create(cls) -> StatsClient:
        client = httpx.AsyncClient(
            base_url=settings.stats_service_url,
            timeout=_TIMEOUT_SECONDS,
            event_hooks={"request": [_inject_trace]},
        )
        return cls(client)

    async def get_summary(
        self, short_code: str | None = None, days: int | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if short_code:
            params["short_code"] = short_code
        if days:
            params["days"] = days
        response = await self._client.get("/api/stats/summary", params=params)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    async def delete_clicks(self, short_code: str) -> None:
        response = await self._client.delete(
            f"/api/clicks/{short_code}",
            headers={"X-Internal-Token": settings.internal_api_token},
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
