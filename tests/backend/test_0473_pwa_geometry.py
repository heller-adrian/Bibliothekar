"""0.47.3: reproduzierbare Viewport-/Sticky-Korrektur für die installierte PWA."""
from app import __version__, main
from app.ui_shell import (
    BIBLIOTHEKAR_0473_CSS,
    BIBLIOTHEKAR_0473_VIEWPORT_JS,
    apply_shell,
)


def _page(area):
    return apply_shell(
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '</head><body><main></main></body></html>',
        active_area=area,
        subarea="captures" if area == "workspace" else None,
    )


def test_0473_version_and_logo_v2_unchanged():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.50.2"
    for area in ("import", "workspace", "archive", "metadata", "trash"):
        page = _page(area)
        assert page.count('src="/assets/bibliothekar-logo-v2.svg?v=0.47.3"') == 2
        assert page.count('id="bk-current-library-name"') == 1
        assert "<style>" + BIBLIOTHEKAR_0473_CSS + "</style>" in page


def test_0473_viewport_is_corrected_before_body_only_for_standalone():
    js = BIBLIOTHEKAR_0473_VIEWPORT_JS
    assert 'root.dataset.bkDisplayMode !== "standalone"' in js
    assert 'window.matchMedia?.("(max-width: 820px)")' in js
    assert 'viewport-fit\\s*=\\s*cover' in js
    assert 'viewport.setAttribute("content", normalized)' in js
    assert 'root.dataset.bkViewportNormalized = "true"' in js
    page = _page("workspace")
    assert "<script>" + js + "</script>" in page
    assert page.index("<script>" + js + "</script>") < page.index("</head>")
    assert page.index("</head>") < page.index("<body")


def test_0473_subnav_uses_normal_flow_without_negative_margin():
    css = BIBLIOTHEKAR_0473_CSS
    assert 'data-bk-area="workspace"] > .bk-workspace-subnav' in css
    assert 'data-bk-area="metadata"] > .bk-metadata-subnav' in css
    assert "margin-top:0 !important" in css
    assert "padding-top:8px !important" in css
    assert "position:sticky !important" in css
    assert "top:0 !important" in css
    assert "margin-top:12px !important" in css
    assert "padding-top:0 !important" in css
    assert "margin-top:-26px" not in css
    assert "transform:translateY" not in css


def test_0473_tasks_circle_only_shrinks_not_text():
    css = BIBLIOTHEKAR_0473_CSS
    assert ".bk-pwa-task-toggle .bk-pwa-task-count" in css
    assert "width:33px !important" in css
    assert "height:33px !important" in css
    assert "min-width:33px !important" in css
    assert "font-size:.85rem !important" in css
    assert ".bk-pwa-dock {" not in css
    assert 'html[data-bk-display-mode="browser"]' not in css
