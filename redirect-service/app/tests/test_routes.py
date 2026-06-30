"""Integration tests for the link API and the redirect hot path."""

from datetime import UTC, datetime, timedelta

from app.models.link import Link
from app.tests.conftest import Ctx


async def test_create_link_returns_short_url(api: Ctx) -> None:
    resp = await api.client.post("/api/links", json={"original_url": "https://example.com/page"})
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["short_code"]) == 7
    assert body["short_url"].endswith("/" + body["short_code"])
    assert body["original_url"].startswith("https://example.com")


async def test_create_link_rejects_invalid_url(api: Ctx) -> None:
    resp = await api.client.post("/api/links", json={"original_url": "not-a-url"})
    assert resp.status_code == 422


async def test_create_link_requires_internal_token(api: Ctx) -> None:
    resp = await api.client.post(
        "/api/links",
        json={"original_url": "https://example.com"},
        headers={"X-Internal-Token": "wrong-token"},
    )
    assert resp.status_code == 401


async def test_list_links_requires_internal_token(api: Ctx) -> None:
    resp = await api.client.get("/api/links", headers={"X-Internal-Token": "wrong-token"})
    assert resp.status_code == 401


async def test_delete_link_removes_and_purges_cache(api: Ctx) -> None:
    created = await api.client.post("/api/links", json={"original_url": "https://example.com/del"})
    code = created.json()["short_code"]
    await api.client.get(f"/{code}", follow_redirects=False)  # warm cache
    assert code in api.cache.store

    resp = await api.client.delete(f"/api/links/{code}")
    assert resp.status_code == 204
    assert code not in api.cache.store  # Redis entry purged

    gone = await api.client.get(f"/{code}", follow_redirects=False)
    assert gone.status_code == 404  # removed from DB


async def test_delete_link_requires_internal_token(api: Ctx) -> None:
    resp = await api.client.delete(
        "/api/links/abc1234", headers={"X-Internal-Token": "wrong-token"}
    )
    assert resp.status_code == 401


async def test_redirect_miss_then_cache_hit_and_emits(api: Ctx) -> None:
    created = await api.client.post("/api/links", json={"original_url": "https://example.com/x"})
    code = created.json()["short_code"]
    target = created.json()["original_url"]

    # Cache is cold before the first hit.
    assert code not in api.cache.store

    first = await api.client.get(f"/{code}", follow_redirects=False)
    assert first.status_code == 302
    assert first.headers["location"] == target
    # Cache warmed on the miss.
    assert api.cache.store[code] == target
    # Click recorded via background task — redirect itself never waited on stats.
    assert len(api.events) == 1
    assert api.events[0].short_code == code

    # Second hit is served from cache and still counts the click.
    second = await api.client.get(f"/{code}", follow_redirects=False)
    assert second.status_code == 302
    assert second.headers["location"] == target
    assert len(api.events) == 2


async def test_redirect_unknown_code_returns_404(api: Ctx) -> None:
    resp = await api.client.get("/zzzzzzz", follow_redirects=False)
    assert resp.status_code == 404
    assert api.events == []


async def test_redirect_expired_link_returns_404(api: Ctx) -> None:
    async with api.session_factory() as session:
        session.add(
            Link(
                short_code="expired1",
                original_url="https://gone.example.com/",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await session.commit()

    resp = await api.client.get("/expired1", follow_redirects=False)
    assert resp.status_code == 404


async def test_list_links_filters_by_owner(api: Ctx) -> None:
    await api.client.post(
        "/api/links", json={"original_url": "https://a.example.com", "owner_id": 1}
    )
    await api.client.post(
        "/api/links", json={"original_url": "https://b.example.com", "owner_id": 2}
    )

    resp = await api.client.get("/api/links", params={"owner_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["owner_id"] == 1
