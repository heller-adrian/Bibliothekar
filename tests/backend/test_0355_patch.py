from __future__ import annotations

from app import main
from app.ui_shell import BIBLIOTHEKAR_0355_CSS
from app.workspace_ui import WORKSPACE_HTML


def test_0355_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.45.6"


def test_0355_capture_summary_targets_real_markup_and_is_compact():
    css = BIBLIOTHEKAR_0355_CSS
    assert ".bk-capture-summary-slot > section.summary" in css
    assert ".bk-capture-summary-slot > section.summary > .card" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;" in css
    assert "height: 40px !important;" in css
    assert "flex-direction: row !important;" in css
    assert "font-size: .68rem !important;" in css
    assert "font-size: 1rem !important;" in css


def test_0355_pwa_dock_has_more_bottom_clearance_everywhere():
    css = BIBLIOTHEKAR_0355_CSS
    assert "padding-bottom: 16px !important;" in css
    assert "padding-bottom: 64px !important;" in css
    assert "bottom: 62px !important;" in css


def test_0355_backup_filter_long_names_can_wrap():
    assert "grid-template-columns:auto minmax(0,1fr) auto" in WORKSPACE_HTML
    assert ".backup-filter-choice strong" in WORKSPACE_HTML
    assert "overflow-wrap:anywhere" in WORKSPACE_HTML
    assert "word-break:break-word" in WORKSPACE_HTML
