"""Schema for the click event sent to the stats-service."""

from datetime import datetime

from pydantic import BaseModel


class ClickEvent(BaseModel):
    short_code: str
    user_agent: str | None = None
    referer: str | None = None
    ip_hash: str | None = None
    timestamp: datetime
