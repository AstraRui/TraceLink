"""HTTP client for talking to redirect-service.

Every request carries the shared ``internal_api_token`` in the
``X-Internal-Token`` header — redirect-service rejects link-management calls
without it.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import trace_id_var

_TIMEOUT_SECONDS = 5.0


async def _inject_trace(request: httpx.Request) -> None:
    request.headers["X-Request-ID"] = trace_id_var.get()


class RedirectClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def create(cls) -> RedirectClient:
        client = httpx.AsyncClient(
            base_url=settings.redirect_service_url,
            headers={"X-Internal-Token": settings.internal_api_token},
            timeout=_TIMEOUT_SECONDS,
            event_hooks={"request": [_inject_trace]},
        )
        return cls(client)

    async def create_link(
        self,
        *,
        original_url: str,
        owner_id: int,
        is_private: bool = False,
        ttl_days: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "original_url": original_url,
            "owner_id": owner_id,
            "is_private": is_private,
        }
        if ttl_days is not None:
            payload["ttl_days"] = ttl_days
        response = await self._client.post("/api/links", json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    async def list_links(self, owner_id: int) -> list[dict[str, Any]]:
        response = await self._client.get("/api/links", params={"owner_id": owner_id})
        response.raise_for_status()
        data: list[dict[str, Any]] = response.json()
        return data

    async def delete_link(self, short_code: str) -> None:
        response = await self._client.delete(f"/api/links/{short_code}")
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
