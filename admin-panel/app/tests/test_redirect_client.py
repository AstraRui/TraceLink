"""Tests for the redirect-service HTTP client (mocked transport, no network)."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services.redirect_client import RedirectClient


async def test_create_link_sends_token_and_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["token"] = request.headers.get("x-internal-token")
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"short_code": "abc1234"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://redirect",
        headers={"X-Internal-Token": "tok-123"},
    )
    rc = RedirectClient(client)
    result = await rc.create_link(original_url="https://e.com", owner_id=7, ttl_days=5)
    await rc.aclose()

    assert result["short_code"] == "abc1234"
    assert captured["token"] == "tok-123"
    assert captured["body"] == {
        "original_url": "https://e.com",
        "owner_id": 7,
        "is_private": False,
        "ttl_days": 5,
    }


async def test_create_link_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid token"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://redirect")
    rc = RedirectClient(client)
    with pytest.raises(httpx.HTTPStatusError):
        await rc.create_link(original_url="https://e.com", owner_id=1)
    await rc.aclose()


async def test_list_links_passes_owner_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("owner_id") == "3"
        return httpx.Response(200, json=[{"short_code": "a"}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://redirect")
    rc = RedirectClient(client)
    items = await rc.list_links(owner_id=3)
    await rc.aclose()
    assert items[0]["short_code"] == "a"


async def test_factory_uses_internal_token_header() -> None:
    rc = RedirectClient.create()
    try:
        assert rc._client.headers["x-internal-token"] == settings.internal_api_token
    finally:
        await rc.aclose()
