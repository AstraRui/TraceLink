"""DB-side aggregation of click statistics.

Every method pushes the work into SQL (COUNT + GROUP BY) and returns only the
small aggregated result set — raw click rows are never loaded into Python.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click
from app.schemas.stats import CodeCount, DayCount, NameCount

BreakdownField = Literal["browser", "os", "device_type"]

_BREAKDOWN_COLUMNS = {
    "browser": Click.browser,
    "os": Click.os,
    "device_type": Click.device_type,
}


class StatsAggregator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _since(days: int) -> datetime:
        return datetime.now(UTC) - timedelta(days=days)

    def _apply_filters(
        self, stmt: Select[Any], short_code: str | None, days: int | None
    ) -> Select[Any]:
        if short_code is not None:
            stmt = stmt.where(Click.short_code == short_code)
        if days is not None:
            stmt = stmt.where(Click.created_at >= self._since(days))
        return stmt

    async def total_clicks(self, short_code: str | None = None, days: int | None = None) -> int:
        stmt = self._apply_filters(select(func.count()).select_from(Click), short_code, days)
        return int(await self.session.scalar(stmt) or 0)

    async def clicks_by_day(
        self, short_code: str | None = None, days: int | None = 30
    ) -> list[DayCount]:
        day = func.date(Click.created_at)
        stmt = self._apply_filters(
            select(day.label("day"), func.count().label("clicks")), short_code, days
        )
        stmt = stmt.group_by(day).order_by(day)
        rows = await self.session.execute(stmt)
        return [DayCount(day=str(row.day), clicks=row.clicks) for row in rows]

    async def top_links(self, limit: int = 10, days: int | None = None) -> list[CodeCount]:
        stmt = self._apply_filters(
            select(Click.short_code.label("code"), func.count().label("clicks")),
            None,
            days,
        )
        stmt = stmt.group_by(Click.short_code).order_by(func.count().desc()).limit(limit)
        rows = await self.session.execute(stmt)
        return [CodeCount(short_code=row.code, clicks=row.clicks) for row in rows]

    async def breakdown(
        self,
        field: BreakdownField,
        short_code: str | None = None,
        days: int | None = None,
    ) -> list[NameCount]:
        column = _BREAKDOWN_COLUMNS[field]
        stmt = self._apply_filters(
            select(column.label("name"), func.count().label("clicks")),
            short_code,
            days,
        )
        stmt = stmt.group_by(column).order_by(func.count().desc())
        rows = await self.session.execute(stmt)
        return [NameCount(name=row.name or "Unknown", clicks=row.clicks) for row in rows]
