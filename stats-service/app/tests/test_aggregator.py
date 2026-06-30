"""Tests for DB-side statistics aggregation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click
from app.services.aggregator import StatsAggregator


async def _seed(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    session.add_all(
        [
            Click(
                short_code="aaaaaa",
                browser="Chrome",
                os="Windows",
                device_type="pc",
                created_at=now,
            ),
            Click(
                short_code="aaaaaa",
                browser="Chrome",
                os="Windows",
                device_type="pc",
                created_at=now,
            ),
            Click(
                short_code="aaaaaa",
                browser="Safari",
                os="iOS",
                device_type="mobile",
                created_at=yesterday,
            ),
            Click(
                short_code="bbbbbb", browser="Firefox", os="Linux", device_type="pc", created_at=now
            ),
        ]
    )
    await session.commit()


async def test_total_clicks(session: AsyncSession) -> None:
    await _seed(session)
    agg = StatsAggregator(session)
    assert await agg.total_clicks() == 4
    assert await agg.total_clicks(short_code="aaaaaa") == 3


async def test_top_links_ordered_by_count(session: AsyncSession) -> None:
    await _seed(session)
    top = await StatsAggregator(session).top_links()
    assert top[0].short_code == "aaaaaa"
    assert top[0].clicks == 3
    assert top[1].short_code == "bbbbbb"
    assert top[1].clicks == 1


async def test_breakdown_by_device(session: AsyncSession) -> None:
    await _seed(session)
    devices = {d.name: d.clicks for d in await StatsAggregator(session).breakdown("device_type")}
    assert devices == {"pc": 3, "mobile": 1}


async def test_breakdown_filtered_by_code(session: AsyncSession) -> None:
    await _seed(session)
    browsers = {
        b.name: b.clicks
        for b in await StatsAggregator(session).breakdown("browser", short_code="aaaaaa")
    }
    assert browsers == {"Chrome": 2, "Safari": 1}


async def test_clicks_by_day_groups_by_date(session: AsyncSession) -> None:
    await _seed(session)
    by_day = await StatsAggregator(session).clicks_by_day(short_code="aaaaaa", days=30)
    assert len(by_day) == 2  # today + yesterday
    assert sum(d.clicks for d in by_day) == 3
