from __future__ import annotations

from app import main
from app.ui_shell import BIBLIOTHEKAR_0354_CSS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML


def test_0354_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.47.8"


def test_0354_capture_summary_stays_below_title_and_above_workspace_content():
    html = _shell_markup("workspace", "captures")
    assert 'id="bk-capture-summary-slot"' in html

    marker = "function positionWorkspaceChrome()"
    body = WORKSPACE_HTML[
        WORKSPACE_HTML.index(marker):
        WORKSPACE_HTML.index("window.addEventListener", WORKSPACE_HTML.index(marker))
    ]
    assert "captureSummarySlot.appendChild(summarySection)" in body


def test_0354_capture_heading_forces_single_column_on_phone():
    css = BIBLIOTHEKAR_0354_CSS
    assert ".bk-page-heading.bk-capture-heading" in css
    assert "display: flex !important;" in css
    assert "flex-direction: column !important;" in css
    assert "grid-template-columns: none !important;" in css
    assert ".bk-capture-summary-slot" in css
    assert "width: 100% !important;" in css


def test_0354_capture_cards_match_archive_compact_2x2_geometry():
    css = BIBLIOTHEKAR_0354_CSS
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;" in css
    assert "gap: 6px !important;" in css
    assert "min-height: 42px !important;" in css
    assert "height: 42px !important;" in css
    assert "flex-direction: row !important;" in css
    assert "align-items: center !important;" in css
    assert "padding: 7px 9px !important;" in css
    assert "border-radius: 10px !important;" in css
    assert "font-size: .68rem !important;" in css
    assert "font-size: 1rem !important;" in css


def test_0354_pwa_dock_has_small_uniform_bottom_clearance():
    css = BIBLIOTHEKAR_0354_CSS
    assert "padding-bottom: 10px !important;" in css
    assert "padding-bottom: 58px !important;" in css
    assert "bottom: 56px !important;" in css
