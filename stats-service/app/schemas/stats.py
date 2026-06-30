"""Response schemas for aggregated statistics."""

from pydantic import BaseModel


class DayCount(BaseModel):
    day: str
    clicks: int


class CodeCount(BaseModel):
    short_code: str
    clicks: int


class NameCount(BaseModel):
    name: str
    clicks: int


class StatsSummary(BaseModel):
    short_code: str | None
    days: int
    total_clicks: int
    clicks_by_day: list[DayCount]
    top_links: list[CodeCount]
    devices: list[NameCount]
    browsers: list[NameCount]
    operating_systems: list[NameCount]
