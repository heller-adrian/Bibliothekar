from __future__ import annotations

from app import main
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.transfer_ui import TRANSFER_HTML
from app.ui_shell import BIBLIOTHEKAR_0353_CSS, BIBLIOTHEKAR_JS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML


def test_0353_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.55.0"


def test_0353_title_help_has_no_visible_question_mark():
    for area, subarea in [
        ("import", None),
        ("workspace", "captures"),
        ("workspace", "events"),
        ("archive", None),
        ("metadata", "library"),
    ]:
        html = _shell_markup(area, subarea)
        assert "data-bk-title-help" in html
        assert "bk-page-help" not in html
    assert "bkToggleTitleHelp" in BIBLIOTHEKAR_JS
    assert ".bk-title-help:hover::after" not in BIBLIOTHEKAR_0353_CSS


def test_0353_archive_subheadings_use_title_help():
    assert '<h2 class="bk-title-help"' in TRANSFER_HTML
    assert 'aria-label="Hilfe zur Archivprüfung"' not in TRANSFER_HTML
    assert 'aria-label="Hilfe zum Archivverlauf"' not in TRANSFER_HTML


def test_0353_metadata_area_help_is_on_title():
    assert 'id="meta-area-help"' not in METADATA_CORRECTION_HTML
    assert 'id="meta-area-title" class="bk-title-help"' in METADATA_CORRECTION_HTML
    assert '$("meta-area-title").dataset.help=areaHelp' in METADATA_CORRECTION_HTML


def test_0353_workspace_summary_moves_before_filter_visually():
    marker = "function positionWorkspaceChrome()"
    body = WORKSPACE_HTML[WORKSPACE_HTML.index(marker):WORKSPACE_HTML.index("window.addEventListener", WORKSPACE_HTML.index(marker))]
    assert "captureSummarySlot.appendChild(summarySection)" in body
    css = BIBLIOTHEKAR_0353_CSS
    assert 'body[data-bk-area="workspace"] .bk-capture-summary-slot .grid.summary' in css
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr)) !important;' in css
    assert 'min-height: 40px !important;' in css


def test_0353_pwa_dock_is_shorter_and_uniform():
    css = BIBLIOTHEKAR_0353_CSS
    assert "padding: 4px 8px 6px !important;" in css
    assert "min-height: 38px !important;" in css
    assert "height: 38px !important;" in css
    assert "bottom: 52px !important;" in css
