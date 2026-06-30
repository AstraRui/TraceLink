"""HTTP routes: lightweight event ingest + aggregated statistics."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import require_internal_token
from app.db.session import get_session
from app.models.click import Click
from app.schemas.event import ClickIn
from app.schemas.stats import StatsSummary
from app.services.aggregator import StatsAggregator
from app.services.parser import parse_user_agent

router = APIRouter()


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: ClickIn, session: AsyncSession = Depends(get_session)) -> Response:
    """Record one click. Deliberately minimal: parse the UA, insert one row.

    Returns 202 immediately — redirect-service fires this in the background, so
    the user's redirect never waits on it.
    """
    parsed = parse_user_agent(event.user_agent)
    session.add(
        Click(
            short_code=event.short_code,
            user_agent=event.user_agent,
            referer=event.referer,
            ip_hash=event.ip_hash,
            browser=parsed.browser,
            os=parsed.os,
            device_type=parsed.device_type,
            created_at=event.timestamp or datetime.now(UTC),
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/stats/summary", response_model=StatsSummary)
async def stats_summary(
    short_code: str | None = None,
    days: int | None = Query(default=None, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> StatsSummary:
    window = days or settings.stats_default_days
    agg = StatsAggregator(session)
    return StatsSummary(
        short_code=short_code,
        days=window,
        total_clicks=await agg.total_clicks(short_code, window),
        clicks_by_day=await agg.clicks_by_day(short_code, window),
        top_links=await agg.top_links(settings.top_links_limit, window),
        devices=await agg.breakdown("device_type", short_code, window),
        browsers=await agg.breakdown("browser", short_code, window),
        operating_systems=await agg.breakdown("os", short_code, window),
    )


@router.delete(
    "/clicks/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_internal_token)],
)
async def delete_clicks(short_code: str, session: AsyncSession = Depends(get_session)) -> Response:
    """Delete every click for a short code (cascade from a link deletion)."""
    await session.execute(delete(Click).where(Click.short_code == short_code))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
