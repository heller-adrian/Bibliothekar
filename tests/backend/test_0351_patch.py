from __future__ import annotations

from app import main
from app.ui_shell import (
    BIBLIOTHEKAR_0351_CSS,
    BIBLIOTHEKAR_JS,
    _shell_markup,
)


def test_0351_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.56.2"


def test_0351_pwa_popovers_use_visible_triggers():
    html = _shell_markup("import", None)
    assert 'id="bk-pwa-task-button"' in html
    assert 'id="bk-pwa-menu-button"' in html
    assert "pwaTasksButton?.addEventListener" in BIBLIOTHEKAR_JS
    assert "pwaMenuButton?.addEventListener" in BIBLIOTHEKAR_JS
    assert "function openTaskPanel()" in BIBLIOTHEKAR_JS
    assert "const anchor = arguments[0] || tasksButton" in BIBLIOTHEKAR_JS
    assert "function openMenu()" in BIBLIOTHEKAR_JS
    assert "const anchor = arguments[0] || menuButton" in BIBLIOTHEKAR_JS


def test_0351_standalone_header_is_fixed_compact_and_shows_library():
    css = BIBLIOTHEKAR_0351_CSS
    assert 'html[data-bk-display-mode="standalone"] .bk-shell' in css
    assert "position: fixed;" in css
    assert 'html[data-bk-display-mode="standalone"] .bk-brand-library' in css
    assert "display: block !important;" in css
    assert 'padding-top: var(--bk-shell-sticky-height' in css


def test_0351_workspace_actions_dock_in_mobile_web_app():
    source = open("app/workspace_ui.py", encoding="utf-8").read()
    css = BIBLIOTHEKAR_0351_CSS
    assert "function workspaceStandaloneMobile()" in source
    assert "function workspaceHeaderDock()" in source
    assert "if(workspaceHeaderDock() && selectionDockTarget)" in source
    assert ".selection-bar.is-header-docked" in css
    assert ".selection-top-button" in css


def test_0351_metadata_second_header_order_and_mobile_status_layout():
    html = _shell_markup("metadata", "multiple")
    assert html.index("Bibliothek</a>") < html.index("Allgemein</a>") < html.index("Mehrfachkorrektur</a>")
    css = BIBLIOTHEKAR_0351_CSS
    assert ".bk-metadata-subnav" in css
    assert ".bk-status-card .status-label" in css
    assert "grid-column: 1 / -1;" in css
    assert ".bk-pwa-task-toggle" in css
    assert ".bk-pwa-task-count" in css
