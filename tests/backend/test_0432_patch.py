from app.events_ui import EVENTS_HTML
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_shell import BIBLIOTHEKAR_JS
from app.workspace_ui import WORKSPACE_HTML
from app import main


def test_0432_shell_measures_secondary_sticky_bottom():
    assert "--bk-secondary-sticky-bottom" in BIBLIOTHEKAR_JS
    assert 'document.querySelector(".bk-workspace-subnav")' in BIBLIOTHEKAR_JS
    assert "new ResizeObserver(()=>syncShellStickyHeight())" in BIBLIOTHEKAR_JS


def test_0432_workspace_preview_sticks_below_secondary_header_and_scrolls_itself():
    assert "top: calc(var(--bk-secondary-sticky-bottom, 141px) + 12px);" in WORKSPACE_HTML
    assert "max-height: calc(100dvh - var(--bk-secondary-sticky-bottom, 141px) - 24px);" in WORKSPACE_HTML
    assert ".preview #structure-preview" in WORKSPACE_HTML
    assert "overflow-y: auto;" in WORKSPACE_HTML
    assert "overscroll-behavior: contain;" in WORKSPACE_HTML


def test_0432_metadata_detail_sticks_below_secondary_header():
    assert "#meta-detail-card," in METADATA_CORRECTION_HTML
    assert "#multi-detail-card{" in METADATA_CORRECTION_HTML
    assert "top:calc(var(--bk-secondary-sticky-bottom,141px) + 12px);" in METADATA_CORRECTION_HTML
    assert "max-height:calc(100dvh - var(--bk-secondary-sticky-bottom,141px) - 24px);" in METADATA_CORRECTION_HTML
    assert "overflow:auto;" in METADATA_CORRECTION_HTML


def test_0432_import_ui_has_stage_and_overall_progress_plus_eta():
    html = main.index()
    assert "function stageProgressPercent(job)" in html
    assert "function estimatedRemainingText(job)" in html
    assert "Aktuelle Phase" in html\n    assert "bk-stage-badge" in html
    assert "Gesamt" in html
    assert "Fortschritt gesamt:" in html
    assert "Restzeit:" in html
    assert "overall_progress_current" in html
    assert "stage_progress_current" in html


def test_0432_api_jobs_exposes_stage_and_overall_progress_contract():
    source = open(main.__file__, encoding="utf-8").read()
    assert 'job["stage_progress_stage"] = stage' in source
    assert 'job["stage_progress_current"] = stage_current' in source
    assert 'job["stage_progress_total"] = stage_total' in source
    assert 'job["overall_progress_current"] = overall' in source
    assert 'job["overall_progress_total"] = 1000' in source


def test_0432_event_edit_submit_uses_busy_spinner():
    assert 'submit.classList.add("bk-busy")' in EVENTS_HTML
    assert 'submit.setAttribute("aria-busy","true")' in EVENTS_HTML
    assert 'await saveEventEditor();' in EVENTS_HTML
    assert 'submit.classList.remove("bk-busy")' in EVENTS_HTML
