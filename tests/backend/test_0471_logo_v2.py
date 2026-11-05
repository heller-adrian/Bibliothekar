"""0.47.3: Die neue SVG-Datei ist in Header und Info-Dialog aktiv."""

from tests.backend.release_contract import EXPECTED_RELEASE_VERSION
from pathlib import Path
import xml.etree.ElementTree as ET

from app import main
from app.ui_shell import apply_shell

ASSETS = Path(__file__).resolve().parents[2] / "app"
OLD = ASSETS / "bibliothekar-logo.svg"
NEW = ASSETS / "bibliothekar-logo-v3.svg"


def test_0471_v2_logo_is_the_selected_asset():
    assert OLD.is_file() and NEW.is_file() and OLD.read_bytes() != NEW.read_bytes()
    old, new = ET.parse(OLD).getroot(), ET.parse(NEW).getroot()
    assert old.attrib["viewBox"] == new.attrib["viewBox"] == "0 0 489.84 133.36"
    text = NEW.read_text(encoding="utf-8")
    assert "stroke: #3b657f" in text
    assert "fill: #fff" in text
    assert "<text" not in text and "font-family" not in text


def test_0471_header_and_about_use_v2_without_old_asset():
    for area in ("import", "workspace", "archive", "metadata", "trash"):
        html = apply_shell("<html><head></head><body></body></html>", active_area=area)
        assert html.count('/assets/bibliothekar-logo-v3.svg?v=0.56.2') == 2
        assert '/assets/bibliothekar-logo.svg?v=' not in html
        assert html.count('id="bk-current-library-name"') == 1


def test_0471_asset_endpoint_returns_exact_v2_file():
    response = main.bibliothekar_brand_logo()
    assert Path(response.path) == NEW
    assert response.media_type == "image/svg+xml"
    assert response.headers["x-content-type-options"] == "nosniff"
