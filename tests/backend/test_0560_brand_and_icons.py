"""0.56.2: V3 brand asset, installable icon and stable responsive setup."""

from tests.backend.release_contract import EXPECTED_RELEASE_VERSION
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from starlette.testclient import TestClient
from app import __version__, main, security
from app.main import _library_onboarding_html
from app.security import _login_html
from app.ui_shell import apply_shell, _shell_markup
from app.setup_language import _CSS


ASSETS = Path(__file__).resolve().parents[2] / "app"


def test_0560_assets_are_original_svg_and_blue_icon():
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == EXPECTED_RELEASE_VERSION
    wordmark = (ASSETS / "bibliothekar-logo-v3.svg").read_text(encoding="utf-8")
    background = (ASSETS / "bibliothekar-logo-symbol-background.svg").read_text(encoding="utf-8")
    transparent = (ASSETS / "bibliothekar-logo-symbol.svg").read_text(encoding="utf-8")
    assert ET.fromstring(wordmark).attrib["viewBox"] == "0 0 489.84 133.36"
    assert 'fill: #15222c' not in wordmark
    assert '<rect class="cls-3" width="215" height="215"' in background
    assert 'fill: #15222c' in background
    assert '<rect class="cls-3"' not in transparent
    png = (ASSETS / "bibliothekar-icon-192.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (192, 192)


def test_0560_logo_v3_in_all_ui_surfaces():
    for page in (_login_html(), _library_onboarding_html()):
        assert '/assets/bibliothekar-logo-v3.svg?v=0.56.2' in page
        assert '/assets/bibliothekar-logo-symbol-background.svg?v=0.56.2' in page
        assert 'rel="apple-touch-icon"' in page
        assert 'rel="manifest"' in page
    for area in ("import", "workspace", "archive"):
        html = apply_shell("<html><head></head><body><main></main></body></html>", active_area=area)
        assert html.count('src="/assets/bibliothekar-logo-v3.svg?v=0.56.2"') == 2
        assert '/assets/bibliothekar-logo-symbol-background.svg?v=0.56.2' in html
        assert 'rel="apple-touch-icon"' in html
        assert f'Version <span data-bk-version>{EXPECTED_RELEASE_VERSION}</span>' in html


def test_0560_desktop_centering_without_touching_mobile():
    desktop = _CSS.split("@media(min-width:821px)", 1)[1].split(".bk-setup-lang{", 1)[0]
    assert "left:50%;" in desktop
    assert "transform:translateX(-50%);" in desktop
    assert "width:min(830px,48vw);" in desktop
    assert "position:fixed;" in desktop
    assert "@media(max-width:540px)" in _CSS


def test_0560_endpoints_and_manifest(monkeypatch):
    # Verify public icon routes at the declared URLs, not just bundled assets.
    assert Path(main.bibliothekar_brand_logo().path).name == "bibliothekar-logo-v3.svg"
    assert Path(main.bibliothekar_app_icon_svg().path).name == "bibliothekar-logo-symbol-background.svg"
    assert Path(main.bibliothekar_app_icon_png().path).name == "bibliothekar-icon-192.png"
    from starlette.requests import Request
    for ua in ("Mozilla/5.0 (iPhone)", "Mozilla/5.0 (Macintosh)"):
        request = Request({"type":"http","method":"GET","path":"/manifest.webmanifest",
                           "headers":[(b"user-agent", ua.encode())]})
        manifest = main.web_app_manifest(request).body.decode()
        assert "bibliothekar-icon-192.png" in manifest
        assert "bibliothekar-logo-symbol-background.svg" in manifest
        assert "192x192" in manifest and '"any"' in manifest
        if "iPhone" in ua:
            assert '"portrait-primary"' in manifest
        else:
            assert '"orientation":"any"' in manifest
