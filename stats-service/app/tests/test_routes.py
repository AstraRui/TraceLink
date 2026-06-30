"""Integration tests for event ingest and the stats summary endpoint."""

from sqlalchemy import select

from app.models.click import Click
from app.tests.conftest import Ctx
from app.tests.test_parser import CHROME_WIN, IPHONE


async def test_ingest_event_returns_202_and_parses_ua(api: Ctx) -> None:
    resp = await api.client.post(
        "/api/events", json={"short_code": "aaaaaa", "user_agent": CHROME_WIN}
    )
    assert resp.status_code == 202

    async with api.session_factory() as session:
        rows = (await session.scalars(select(Click))).all()
    assert len(rows) == 1
    assert rows[0].short_code == "aaaaaa"
    assert rows[0].browser == "Chrome"
    assert rows[0].device_type == "pc"


async def test_ingest_requires_short_code(api: Ctx) -> None:
    resp = await api.client.post("/api/events", json={"user_agent": CHROME_WIN})
    assert resp.status_code == 422


async def test_summary_aggregates_all_dimensions(api: Ctx) -> None:
    for ua in (CHROME_WIN, CHROME_WIN, IPHONE):
        await api.client.post("/api/events", json={"short_code": "aaaaaa", "user_agent": ua})
    await api.client.post("/api/events", json={"short_code": "bbbbbb", "user_agent": CHROME_WIN})

    resp = await api.client.get("/api/stats/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_clicks"] == 4
    assert data["top_links"][0] == {"short_code": "aaaaaa", "clicks": 3}
    devices = {d["name"]: d["clicks"] for d in data["devices"]}
    assert devices == {"pc": 3, "mobile": 1}
    browsers = {b["name"]: b["clicks"] for b in data["browsers"]}
    assert browsers["Chrome"] == 3


async def test_summary_filtered_by_short_code(api: Ctx) -> None:
    for ua in (CHROME_WIN, IPHONE):
        await api.client.post("/api/events", json={"short_code": "aaaaaa", "user_agent": ua})
    await api.client.post("/api/events", json={"short_code": "bbbbbb", "user_agent": CHROME_WIN})

    resp = await api.client.get("/api/stats/summary", params={"short_code": "aaaaaa"})
    data = resp.json()
    assert data["short_code"] == "aaaaaa"
    assert data["total_clicks"] == 2


async def test_delete_clicks_removes_only_that_code(api: Ctx) -> None:
    await api.client.post("/api/events", json={"short_code": "aaaaaa", "user_agent": CHROME_WIN})
    await api.client.post("/api/events", json={"short_code": "aaaaaa", "user_agent": IPHONE})
    await api.client.post("/api/events", json={"short_code": "bbbbbb", "user_agent": CHROME_WIN})

    resp = await api.client.delete("/api/clicks/aaaaaa")
    assert resp.status_code == 204

    summary = (await api.client.get("/api/stats/summary")).json()
    assert summary["total_clicks"] == 1  # only "bbbbbb" remains


async def test_delete_clicks_requires_internal_token(api: Ctx) -> None:
    resp = await api.client.delete(
        "/api/clicks/aaaaaa", headers={"X-Internal-Token": "wrong-token"}
    )
    assert resp.status_code == 401
