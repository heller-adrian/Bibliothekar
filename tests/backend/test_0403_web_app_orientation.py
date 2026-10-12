"""0.47.3: iPhone-Web-App bleibt im Hochformat, Tablet und Website bleiben frei."""
import json
from pathlib import Path

from starlette.requests import Request

from app import __version__ as PACKAGE_VERSION
from app import main
from app.ui_shell import apply_shell


def _request(user_agent: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/manifest.webmanifest",
        "query_string": b"",
        "headers": [(b"user-agent", user_agent.encode("utf-8"))],
        "scheme": "https",
        "server": ("bibliothekar.test", 443),
        "client": ("127.0.0.1", 12345),
    })


def _manifest(user_agent: str) -> dict:
    response = main.web_app_manifest(_request(user_agent))
    assert response.media_type == "application/manifest+json"
    assert response.headers["vary"] == "User-Agent"
    return json.loads(response.body)


def test_0403_version_contract():
    assert PACKAGE_VERSION == "0.52.0"
    assert main.APP_VERSION == PACKAGE_VERSION
    assert main.DEPLOYMENT_VERSION == PACKAGE_VERSION
    assert "patch-0.52.0" in Path("compose.example.yaml").read_text(encoding="utf-8")
    assert "Version <span data-bk-version>0.52.0</span>" in Path("app/ui_shell.py").read_text(encoding="utf-8")


def test_0403_shell_links_manifest_without_changing_browser_layout():
    rendered = apply_shell(
        "<!doctype html><html><head></head><body><main></main></body></html>",
        active_area="import",
    )
    assert '<link rel="manifest" href="/manifest.webmanifest">' in rendered
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in rendered


def test_0403_iphone_manifest_locks_installed_web_app_to_portrait_primary():
    data = _manifest(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
        "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    )
    assert data["display"] == "standalone"
    assert data["orientation"] == "portrait-primary"


def test_0403_ipad_and_tablet_manifest_remain_unlocked():
    ipad = _manifest(
        "Mozilla/5.0 (iPad; CPU OS 18_7 like Mac OS X) "
        "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    )
    ipad_desktop_ua = _manifest(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) "
        "AppleWebKit/605.1.15 Version/18.7 Mobile/15E148 Safari/604.1"
    )
    assert ipad["orientation"] == "any"
    assert ipad_desktop_ua["orientation"] == "any"
