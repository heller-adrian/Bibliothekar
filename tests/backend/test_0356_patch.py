from __future__ import annotations

from app import main
from app.ui_shell import BIBLIOTHEKAR_0356_CSS
from app.workspace_ui import WORKSPACE_HTML


def test_0356_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.45.4"


def test_0356_browser_only_rules_do_not_touch_standalone_webapp():
    css = BIBLIOTHEKAR_0356_CSS
    assert 'html[data-bk-display-mode="browser"]' in css
    assert 'html[data-bk-display-mode="standalone"]' not in css


def test_0356_browser_capture_heading_aligns_and_collapses_responsively():
    css = BIBLIOTHEKAR_0356_CSS
    assert "@media (max-width: 920px)" in css
    assert ".bk-page-heading.bk-capture-heading" in css
    assert "width: 100% !important;" in css
    assert "margin: 18px 0 6px !important;" in css
    assert "padding-inline: 18px !important;" in css
    assert "padding-inline: 16px !important;" in css
    assert "padding-inline: 14px !important;" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;" in css
    assert "height: clamp(36px, 5.2vw, 40px) !important;" in css


def test_0356_browser_portrait_uses_webapp_style_workspace_header():
    css = BIBLIOTHEKAR_0356_CSS
    assert "@media (max-width: 700px) and (orientation: portrait)" in css
    assert ".bk-workspace-dock" in css
    assert ".selection-bar.is-header-docked .selection-summary" in css
    assert "display: none !important;" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;" in css

    assert "function workspaceBrowserPortrait()" in WORKSPACE_HTML
    assert 'dataset.bkDisplayMode === "browser"' in WORKSPACE_HTML
    assert 'window.matchMedia("(max-width: 700px) and (orientation: portrait)").matches' in WORKSPACE_HTML
    assert "workspaceBrowserPortrait()" in WORKSPACE_HTML
