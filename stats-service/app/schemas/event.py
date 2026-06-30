"""Schema for an incoming click event (sent by redirect-service)."""

from datetime import datetime

from pydantic import BaseModel


class ClickIn(BaseModel):
    short_code: str
    user_agent: str | None = None
    referer: str | None = None
    ip_hash: str | None = None
    # Click time as recorded by redirect-service; defaults to now() at ingest.
    timestamp: datetime | None = None
