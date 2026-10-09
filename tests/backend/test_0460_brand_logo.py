"""0.47.3: Einheitliches SVG-Markenlogo mit dynamischem Bibliotheksnamen."""
from pathlib import Path
import xml.etree.ElementTree as ET

from app import __version__, main
from app.ui_shell import BIBLIOTHEKAR_0460_CSS, apply_shell


LOGO = Path(__file__).resolve().parents[2] / "app" / "bibliothekar-logo-v2.svg"


def test_0460_svg_is_self_contained_white_and_font_independent():
    assert LOGO.is_file()
    tree = ET.parse(LOGO)
    root = tree.getroot()
    assert root.attrib["viewBox"] == "0 0 489.84 133.36"
    source = LOGO.read_text(encoding="utf-8")
    assert "fill: #fff" in source
    assert "stroke: #3b657f" in source
    assert "fill: #15222c" in source
    assert "<text" not in source
    assert "font-family" not in source
    assert "<script" not in source
    assert "<foreignObject" not in source
    assert "http://" not in source.replace('xmlns="http://www.w3.org/2000/svg"', "")


def test_0460_single_svg_in_all_shell_areas_and_dynamic_library():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.47.6"
    for area, subarea in [
        ("import", None), ("workspace", "captures"), ("workspace", "events"),
        ("archive", None), ("metadata", None), ("trash", None)
    ]:
        page = apply_shell(
            "<!doctype html><html><head></head><body><main></main></body></html>",
            active_area=area,
            subarea=subarea,
        )
        assert page.count('class="bk-brand bk-brand-new"') == 1
        header = page.split('<header class="bk-shell">', 1)[1].split("</header>", 1)[0]
        assert header.count('src="/assets/bibliothekar-logo-v2.svg?v=0.47.3"') == 1
        assert page.count('src="/assets/bibliothekar-logo-v2.svg?v=0.47.3"') == 2
        assert page.count('id="bk-current-library-name"') == 1
        assert "bk-brand-title" not in page.split("<header class=\"bk-shell\">", 1)[1].split("</header>", 1)[0]
        assert 'class="bk-mark"' not in page.split("<header class=\"bk-shell\">", 1)[1].split("</header>", 1)[0]
        assert f"<style>{BIBLIOTHEKAR_0460_CSS}</style>" in page
    shell_code = (LOGO.parent / "ui_shell.py").read_text(encoding="utf-8")
    assert "get_current_library().display_name" in shell_code


def test_0460_brand_asset_is_an_svg_file_response():
    response = main.bibliothekar_brand_logo()
    assert Path(response.path) == LOGO
    assert response.media_type == "image/svg+xml"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_0460_css_preserves_layout_on_mobile_and_desktop():
    css = BIBLIOTHEKAR_0460_CSS
    assert ".bk-brand-new .bk-brand-art" in css
    assert "#bk-current-library-name" in css
    assert "top:71%;" in css
    assert "left:21.5%;" in css
    assert 'html[data-bk-display-mode="standalone"]' in css
    assert "@media (max-width:820px)" in css
    assert "@media (min-width:821px) and (max-width:1120px)" in css
    assert "color:rgba(255,255,255,.80)" in css
