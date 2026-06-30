"""Unit tests for user-agent parsing."""

from app.services.parser import parse_user_agent

CHROME_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def test_parse_desktop_chrome() -> None:
    parsed = parse_user_agent(CHROME_WIN)
    assert parsed.browser == "Chrome"
    assert parsed.os == "Windows"
    assert parsed.device_type == "pc"


def test_parse_mobile_iphone() -> None:
    parsed = parse_user_agent(IPHONE)
    assert parsed.device_type == "mobile"
    assert parsed.os == "iOS"
    assert "Safari" in parsed.browser


def test_parse_bot() -> None:
    assert parse_user_agent(GOOGLEBOT).device_type == "bot"


def test_parse_empty_is_unknown() -> None:
    parsed = parse_user_agent(None)
    assert parsed == parse_user_agent("")
    assert parsed.browser == "Unknown"
    assert parsed.os == "Unknown"
    assert parsed.device_type == "unknown"
