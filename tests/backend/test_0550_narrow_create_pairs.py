"""0.55.1: Mobile event CREATE pairs use measured dialog width, not only CSS queries.

The working 0.54.4 no-event one-day/two-time layout is untouched.
"""
from __future__ import annotations

import re

from app import __version__, main
from app.workspace_ui import WORKSPACE_HTML


def test_0550_compact_create_pairs_win_over_one_column_mobile_rules():
    css=WORKSPACE_HTML.split("<style>",1)[1].split("</style>",1)[0]
    anchor="/* 0.55.0:"
    assert anchor in css
    patch=css.split(anchor,1)[1]
    assert css.index("@media (max-width:460px)") < css.index(anchor)
    assert "#event-dialog.bk-create-pairs #event-form .event-boundary," in patch
    assert "#event-dialog.bk-create-pairs #event-form .create-subevent-boundary {" in patch
    assert "grid-template-columns:minmax(0,3fr) minmax(0,2fr) !important;" in patch
    assert "display:grid !important;" in patch
    assert "grid-column:auto !important;" in patch
    assert "grid-row:auto !important;" in patch
    assert "inline-size:calc(100% - 2px) !important;" in patch
    assert "-webkit-appearance:none !important;" in patch


def test_0550_dialog_width_measured_when_opening_and_resizing():
    script=WORKSPACE_HTML.split("<script>",1)[1]
    assert 'function syncCreateEventCompactPairs()' in script
    assert 'eventDialog.getBoundingClientRect().width' in script
    assert 'document.documentElement.clientWidth' in script
    assert 'dialogWidth<=620 || viewportWidth<=820' in script
    assert 'eventDialog.classList.toggle("bk-create-pairs", compact)' in script
    assert 'new ResizeObserver(syncCreateEventCompactPairs)' in script
    assert 'window.addEventListener("resize",syncCreateEventCompactPairs)' in script
    assert 'eventDialog.showModal();syncCreateEventCompactPairs();scheduleDialogPreview()' in script
    # Dynamic subevent cards inherit the dialog-level class.
    assert 'row.className="create-subevent-card"' in script
    assert 'class="create-subevent-boundary"' in script


def test_0550_no_event_css_and_persistence_remain_identical():
    patch=WORKSPACE_HTML.split("/* 0.55.0:",1)[1].split("</style>",1)[0]
    assert ".no-event-" not in patch
    assert "#no-event-" not in patch
    assert '.no-event-segment-fields > .no-event-day-field' in WORKSPACE_HTML
    assert 'day_key: row.querySelector("[data-segment-day]")?.value' in WORKSPACE_HTML
    assert 'start_time: row.querySelector("[data-segment-start]")?.value' in WORKSPACE_HTML
    assert 'end_time: row.querySelector("[data-segment-end]")?.value' in WORKSPACE_HTML
    assert __version__ == main.DEPLOYMENT_VERSION == "0.55.4"
