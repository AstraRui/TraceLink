"""Pydantic request/response schemas for the link API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class LinkCreate(BaseModel):
    """Payload for creating a new short link."""

    original_url: HttpUrl
    owner_id: int | None = None
    is_private: bool = False
    # Overrides the service default TTL. None = use default; >=1 = days to live.
    ttl_days: int | None = Field(default=None, ge=1)


class LinkRead(BaseModel):
    """Link representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    short_code: str
    original_url: str
    owner_id: int | None
    is_private: bool
    created_at: datetime
    expires_at: datetime | None
    # Full clickable short URL, assembled from BASE_URL by the route layer.
    short_url: str | None = None
