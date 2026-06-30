"""Integration tests for the SSR routes (auth, dashboard, link creation)."""

from app.core.config import settings
from app.models.user import User
from app.services.health import HealthComponent
from app.tests.conftest import Ctx

_QR_PREFIX = "data:image/png;base64,"


async def test_login_page_renders(api: Ctx) -> None:
    resp = await api.client.get("/login")
    assert resp.status_code == 200
    assert "Sign in" in resp.text


async def test_login_success_sets_cookie(api: Ctx) -> None:
    resp = await api.client.post(
        "/login",
        data={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert settings.cookie_name in resp.headers.get("set-cookie", "")
    assert "httponly" in resp.headers.get("set-cookie", "").lower()


async def test_login_failure_shows_error(api: Ctx) -> None:
    resp = await api.client.post(
        "/login",
        data={"username": settings.admin_username, "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.text


async def test_unauthorized_dashboard_redirects_to_login(api: Ctx) -> None:
    resp = await api.client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_dashboard_lists_links_with_qr(api: Ctx) -> None:
    api.redirect_client.links = [
        {
            "id": 1,
            "short_code": "abc1234",
            "short_url": "http://localhost:8080/abc1234",
            "original_url": "https://example.com/x",
            "owner_id": 1,
            "is_private": False,
            "expires_at": None,
        }
    ]
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/")
    assert resp.status_code == 200
    assert "abc1234" in resp.text
    assert _QR_PREFIX in resp.text  # QR generated locally and inlined


async def test_create_link_returns_card(api: Ctx) -> None:
    api.authenticate_as(User(id=7, username="admin"))
    resp = await api.client.post(
        "/links",
        data={"original_url": "https://example.com/page", "ttl_days": "", "is_private": ""},
    )
    assert resp.status_code == 200
    assert "http://localhost:8080/abc1234" in resp.text
    assert _QR_PREFIX in resp.text
    assert api.redirect_client.created[0]["owner_id"] == 7
    assert api.redirect_client.created[0]["is_private"] is False


async def test_create_link_private_checkbox(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    await api.client.post("/links", data={"original_url": "https://e.com", "is_private": "on"})
    assert api.redirect_client.created[0]["is_private"] is True


async def test_create_link_invalid_ttl_returns_error(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.post(
        "/links", data={"original_url": "https://example.com", "ttl_days": "abc"}
    )
    assert resp.status_code == 400
    assert "whole number" in resp.text


async def test_logout_clears_cookie(api: Ctx) -> None:
    resp = await api.client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_stats_fragment_requires_auth(api: Ctx) -> None:
    resp = await api.client.get("/partials/stats", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_stats_fragment_renders_block(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/partials/stats")
    assert resp.status_code == 200
    assert 'id="stats-data"' in resp.text
    assert 'id="chart-by-day"' in resp.text


async def test_stats_json_requires_auth(api: Ctx) -> None:
    resp = await api.client.get("/partials/stats.json", follow_redirects=False)
    assert resp.status_code == 303


async def test_stats_json_returns_summary(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/partials/stats.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_clicks" in data
    assert "clicks_by_day" in data


def _sample_link(code: str = "abc1234") -> dict[str, object]:
    return {
        "id": 1,
        "short_code": code,
        "short_url": f"http://localhost:8080/{code}",
        "original_url": "https://example.com/x",
        "owner_id": 1,
        "is_private": False,
        "expires_at": None,
    }


async def test_delete_link_cascades_to_both_services(api: Ctx) -> None:
    api.redirect_client.links = [_sample_link()]
    api.authenticate_as(User(id=1, username="admin"))

    resp = await api.client.delete("/links/abc1234")
    assert resp.status_code == 200
    # redirect-service called first, then stats-service.
    assert api.redirect_client.deleted == ["abc1234"]
    assert api.stats_client.deleted == ["abc1234"]


async def test_link_detail_renders_per_code_charts(api: Ctx) -> None:
    api.redirect_client.links = [_sample_link()]
    api.authenticate_as(User(id=1, username="admin"))

    resp = await api.client.get("/links/abc1234")
    assert resp.status_code == 200
    assert "abc1234" in resp.text
    assert 'id="chart-by-day"' in resp.text


async def test_link_detail_unknown_redirects_home(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/links/nope999", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


async def test_health_panel_requires_auth(api: Ctx) -> None:
    resp = await api.client.get("/partials/health", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_health_panel_shows_up_and_down(api: Ctx) -> None:
    api.health.components = [
        HealthComponent("PostgreSQL", True),
        HealthComponent("Stats API", False),
    ]
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/partials/health")
    assert resp.status_code == 200
    assert "PostgreSQL" in resp.text
    assert "Stats API" in resp.text
    assert "up" in resp.text and "down" in resp.text


async def test_logs_requires_auth(api: Ctx) -> None:
    resp = await api.client.get("/logs", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_logs_page_renders_rows(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/logs")
    assert resp.status_code == 200
    assert "System Logs" in resp.text
    assert "boom failure" in resp.text
    assert "ERROR" in resp.text


async def test_logs_partial_filters_by_service(api: Ctx) -> None:
    api.authenticate_as(User(id=1, username="admin"))
    resp = await api.client.get("/partials/logs", params={"service": "redirect"})
    assert resp.status_code == 200
    assert "boom failure" in resp.text  # the redirect row
    assert "ADMIN_HOME_RENDERED" not in resp.text  # the admin row is filtered out
