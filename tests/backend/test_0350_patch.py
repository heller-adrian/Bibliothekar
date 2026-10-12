from __future__ import annotations

from app import main
from app.ui_shell import (
    BIBLIOTHEKAR_0350_CSS,
    BIBLIOTHEKAR_BOOTSTRAP_JS,
    _shell_markup,
)


def test_0350_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.53.0"


def test_0350_detects_standalone_web_app_separately_from_browser():
    assert "(display-mode: standalone)" in BIBLIOTHEKAR_BOOTSTRAP_JS
    assert "window.navigator.standalone === true" in BIBLIOTHEKAR_BOOTSTRAP_JS
    assert 'dataset.bkDisplayMode = isStandalone ? "standalone" : "browser"' in BIBLIOTHEKAR_BOOTSTRAP_JS


def test_0350_standalone_shell_uses_reference_header_and_bottom_dock():
    html = _shell_markup("workspace", "captures")
    assert 'class="bk-pwa-dock"' in html
    assert 'data-area="import"' in html
    assert 'data-area="workspace"' in html
    assert 'data-area="archive"' in html
    assert 'data-bk-task-count' in html
    assert 'aria-label="Menü öffnen"' in html

    assert 'html[data-bk-display-mode="standalone"] .bk-tabs' in BIBLIOTHEKAR_0350_CSS
    assert 'html[data-bk-display-mode="standalone"] .bk-shell-actions' in BIBLIOTHEKAR_0350_CSS
    assert 'html[data-bk-display-mode="standalone"] .bk-pwa-dock' in BIBLIOTHEKAR_0350_CSS


def test_0350_mobile_content_fixes_apply_to_browser_and_web_app():
    assert "@media (max-width: 700px)" in BIBLIOTHEKAR_0350_CSS
    assert ".bk-metadata-subnav .bk-workspace-links" in BIBLIOTHEKAR_0350_CSS
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in BIBLIOTHEKAR_0350_CSS
    assert "#event-dialog .create-subevent-top" in BIBLIOTHEKAR_0350_CSS
    assert "#event-dialog .create-subevent-remove" in BIBLIOTHEKAR_0350_CSS
    assert ".bk-status-grid" in BIBLIOTHEKAR_0350_CSS


def test_0350_workspace_standalone_is_compact():
    assert 'body[data-bk-area="workspace"] .grid.summary' in BIBLIOTHEKAR_0350_CSS
    assert "repeat(4, minmax(0, 1fr))" in BIBLIOTHEKAR_0350_CSS
    assert 'body[data-bk-area="workspace"] .day-card' in BIBLIOTHEKAR_0350_CSS


def test_0350_import_schema_status_is_compact_range():
    source = open("app/main.py", encoding="utf-8").read()
    assert "const schemaSummary = schemaVersions.length > 1" in source
    assert 'schemaVersions[0] + "–" + schemaVersions[schemaVersions.length - 1]' in source
