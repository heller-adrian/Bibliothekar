"""0.54.5: Later mobile shell may not undo the create-event two-column grid.

The 0.54.4 tests validated its source CSS but missed that the assembled page
adds ui_shell CSS AFTER the workspace stylesheet. The equal-specificity
!important mobile shell rule silently stacked both create date/time pairs.
"""
from __future__ import annotations

from app import __version__, main
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.ui_shell import BIBLIOTHEKAR_0350_CSS


def test_0545_narrow_create_dates_and_times_stay_on_one_row_after_shell_css():
    workspace_css = WORKSPACE_HTML.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "@container mobile-event-create (max-width:620px)" in workspace_css
    assert "#event-form .event-boundary," in workspace_css
    assert "#event-form .create-subevent-boundary {" in workspace_css
    assert "grid-template-columns:minmax(0,3fr) minmax(0,2fr) !important;" in workspace_css
    # The shell is injected after the workspace stylesheet. It MUST NOT
    # re-introduce !important one-column rules for each inner date/time pair.
    assert "#event-dialog .event-boundary {" not in BIBLIOTHEKAR_0350_CSS
    assert "#event-dialog .create-subevent-boundary," not in BIBLIOTHEKAR_0350_CSS
    assert "#event-dialog .create-subevent-boundary {" not in BIBLIOTHEKAR_0350_CSS
    # The outer list of child boundaries may remain stacked: start and end
    # are two separate lines, with date and time adjacent WITHIN each line.
    assert """#event-dialog .create-subevent-boundaries {
    grid-template-columns: minmax(0, 1fr) !important;""" in BIBLIOTHEKAR_0350_CSS


def test_0545_create_inputs_and_existing_subevent_markup_remain_intact():
    for fragment in (
        'id="event-start-date" type="date"',
        'id="event-start-time" type="time"',
        'id="event-end-date" type="date"',
        'id="event-end-time" type="time"',
        'class="create-subevent-boundary"',
        'data-create-child-start-date',
        'data-create-child-start-time',
        'data-create-child-end-date',
        'data-create-child-end-time',
    ):
        assert fragment in WORKSPACE_HTML, fragment


def test_0545_no_event_and_edit_event_stay_unchanged():
    css = WORKSPACE_HTML.split("<style>", 1)[1].split("</style>", 1)[0]
    # Retain the exact day + two time row rules from 0.54.4.
    no_event_css = css.split('/* "Ohne Ereignis": a single selected DAY', 1)[1]
    assert '#event-form .no-event-segment-fields > .no-event-day-field' in no_event_css
    assert '#event-form .no-event-segment-fields > .no-event-start-field' in no_event_css
    assert '#event-form .no-event-segment-fields > .no-event-end-field' in no_event_css
    assert '#event-form .no-event-end-date-mirror { display:none !important; }' in no_event_css
    assert 'grid-template-columns:repeat(2,minmax(0,1fr)) !important;' in no_event_css
    assert "/* 0.54.3:" in EVENTS_HTML
    assert __version__ == main.DEPLOYMENT_VERSION == "0.54.5"
