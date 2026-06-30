"""Fire-and-forget delivery of click events to the stats-service.

The redirect handler schedules :func:`send_click_event` as a background task, so
the user's redirect is returned *before* this runs. Any delivery failure is
logged and swallowed — an unavailable stats-service must never affect redirects.
"""

import logging
from collections.abc import Awaitable, Callable

import httpx

from app.core.config import settings
from app.schemas.event import ClickEvent

logger = logging.getLogger(__name__)

# Type of the injectable emitter (real sender in prod, recorder/no-op in tests).
# Takes the event and the trace id captured when the redirect was handled.
ClickEmitter = Callable[[ClickEvent, str], Awaitable[None]]

_STATS_EVENTS_PATH = "/api/events"
_TIMEOUT_SECONDS = 2.0


async def send_click_event(event: ClickEvent, trace_id: str) -> None:
    url = f"{settings.stats_service_url}{_STATS_EVENTS_PATH}"
    # Forward the trace id so stats-service logs the ingest under the same trace.
    headers = {"X-Request-ID": trace_id}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            await client.post(url, json=event.model_dump(mode="json"), headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("click event delivery failed: %s", exc)


def get_click_emitter() -> ClickEmitter:
    """FastAPI dependency: the click emitter (overridable in tests)."""
    return send_click_event
