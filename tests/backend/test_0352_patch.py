from __future__ import annotations

from app import main
from app.events_ui import EVENTS_HTML
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.transfer_ui import TRANSFER_HTML
from app.ui_shell import BIBLIOTHEKAR_0352_CSS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML


def test_0352_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.46.0"


def test_0352_page_subtitles_remain_compact_help():
    for area, subarea in [
        ("import", None),
        ("workspace", "captures"),
        ("workspace", "events"),
        ("archive", None),
        ("metadata", "library"),
    ]:
        html = _shell_markup(area, subarea)
        assert "data-bk-title-help" in html
    assert "Freie Aufnahmen ordnen und Ereignisse aus dem Arbeitsbestand bilden.</p>" not in _shell_markup("workspace", "captures")


def test_0352_workspace_filter_and_neutral_placeholders():
    assert "backup-filter-icon" in WORKSPACE_HTML
    assert "Zum Beispiel Urlaub" in WORKSPACE_HTML
    assert "Zum Beispiel Tag 1" in WORKSPACE_HTML
    assert "Zum Beispiel Israel" not in WORKSPACE_HTML
    assert "Zum Beispiel Konzert" not in WORKSPACE_HTML


def test_0352_import_removes_diagnostics_and_moves_source_help():
    source = open("app/main.py", encoding="utf-8").read()
    assert "Diagnose &amp; Test" not in source
    assert "Testimport starten" not in source
    assert 'id="test-button"' not in source
    assert "Quelle auswählen und anschließend sicher einlesen." in source
    assert '<div class="bk-source-mode-note">Quelle auswählen' not in source


def test_0352_events_and_archive_explanations_are_compact():
    assert "Planung, Prüfung und bestätigte Sortierung" not in EVENTS_HTML
    assert 'data-help="Neu angewendete Ereignisse werden hier geprüft' in TRANSFER_HTML
    assert 'data-help="Freigegebene Ereignisse bleiben hier nachvollziehbar.' in TRANSFER_HTML


def test_0352_metadata_order_hidden_contract_and_path_wrapping():
    html = _shell_markup("metadata", "library")
    assert html.index("Bibliothek</a>") < html.index("Allgemein</a>") < html.index("Mehrfachkorrektur</a>")
    assert "[hidden]{display:none!important}" in METADATA_CORRECTION_HTML
    assert "overflow-wrap:anywhere" in METADATA_CORRECTION_HTML
    assert 'id="meta-area-title"' in METADATA_CORRECTION_HTML
    assert "data-bk-title-help" in METADATA_CORRECTION_HTML


def test_0352_web_app_dock_and_compact_stats_contract():
    css = BIBLIOTHEKAR_0352_CSS
    html = _shell_markup("workspace", "captures")
    assert '<span class="bk-pwa-icon" aria-hidden="true">✓</span>' not in html
    assert 'id="bk-pwa-task-button"' in html
    assert "max(10px, env(safe-area-inset-bottom))" in css
    assert 'grid-template-columns: repeat(4, minmax(0, 1fr)) !important;' in css
    assert 'body[data-bk-area="archive"] .grid.summary' in css
    assert 'width: calc(100% - 38px);' in css


def test_0352_mobile_summary_uses_capture_header_slot():
    source = WORKSPACE_HTML
    marker = "function positionWorkspaceChrome()"
    body = source[source.index(marker):source.index("window.addEventListener", source.index(marker))]
    assert "captureSummarySlot.appendChild(summarySection)" in body
    assert 'classList.toggle("compact-heading-summary", workspaceStaticDesktop())' in body
