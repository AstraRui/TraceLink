"""User-agent parsing into browser / OS / device type.

Uses the offline ``user-agents`` library (no network lookups). Parsing happens
once at ingest time so aggregation is a plain GROUP BY with no re-parsing.
"""

from dataclasses import dataclass
from typing import Any

from user_agents import parse as ua_parse

UNKNOWN = "Unknown"


@dataclass(frozen=True)
class ParsedUA:
    browser: str
    os: str
    device_type: str  # mobile | tablet | pc | bot | other | unknown


def _device_type(ua: Any) -> str:
    if ua.is_bot:
        return "bot"
    if ua.is_mobile:
        return "mobile"
    if ua.is_tablet:
        return "tablet"
    if ua.is_pc:
        return "pc"
    return "other"


def parse_user_agent(user_agent: str | None) -> ParsedUA:
    if not user_agent:
        return ParsedUA(browser=UNKNOWN, os=UNKNOWN, device_type="unknown")
    ua = ua_parse(user_agent)
    return ParsedUA(
        browser=ua.browser.family or UNKNOWN,
        os=ua.os.family or UNKNOWN,
        device_type=_device_type(ua),
    )
