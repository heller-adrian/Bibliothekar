"""0.54.4 responsive create-event editor layout regression tests.

Only the narrow create dialog may change. The proven edit-event correction
remains untouched, as do desktop create forms and the no-event day_key model.
"""
from __future__ import annotations

import re

from app import __version__, main
from app.workspace_ui import WORKSPACE_HTML


def _create_styles():
    return WORKSPACE_HTML.split("<style>",1)[1].split("</style>",1)[0]


def test_0544_mobile_rules_are_container_scoped_and_follow_old_mobile_css():
    css=_create_styles()
    marker="/* 0.54.4:"
    assert marker in css
    patch=css.split(marker,1)[1]
    assert '#event-dialog { container-type:inline-size; container-name:mobile-event-create; }' in patch
    assert '@container mobile-event-create (max-width:620px)' in patch
    assert css.index('@media (max-width:460px)') < css.index(marker)
    assert '#event-form .event-boundary,' in patch
    assert '#event-form .create-subevent-boundary' in patch
    assert 'grid-template-columns:minmax(0,3fr) minmax(0,2fr) !important;' in patch
    # No global rule, no alteration to the already working edit-event dialog.
    assert '#event-edit-dialog' not in patch
    assert '.event-boundary{' not in patch
    assert '#event-dialog' in patch


def test_0544_create_and_dynamic_child_fields_share_responsive_layout():
    html=WORKSPACE_HTML
    assert 'id="event-start-date" type="date"' in html
    assert 'id="event-start-time" type="time"' in html
    assert 'id="event-end-date" type="date"' in html
    assert 'id="event-end-time" type="time"' in html
    assert 'class="create-subevent-boundary"' in html
    assert 'data-create-child-start-date' in html
    assert 'data-create-child-end-time' in html
    css=_create_styles().split("/* 0.54.4:",1)[1]
    assert '-webkit-appearance:none !important;' in css
    assert 'inline-size:calc(100% - 2px) !important;' in css
    assert 'padding:0 !important;' in css
    assert 'align-items:center;' in css
    assert 'justify-content:center;' in css


def test_0544_no_event_uses_one_day_and_a_separate_two_time_row():
    css=_create_styles().split("/* 0.54.4:",1)[1]
    for required in (
        '.no-event-mobile-range-title,',
        '.no-event-end-date-mirror { display:none !important; }',
        '.no-event-segment-fields > .no-event-day-field',
        'grid-column:1 / -1 !important;',
        'grid-row:1 !important;',
        '.no-event-segment-fields > .no-event-start-field',
        'grid-column:1 !important;',
        '.no-event-segment-fields > .no-event-end-field',
        'grid-column:2 !important;',
        'grid-row:2 !important;',
        'grid-template-columns:repeat(2,minmax(0,1fr)) !important;',
    ):
        assert required in css, required
    # Save path still reads exactly one canonical day_key and two times;
    # the former mirror remains only in the legacy markup for desktop.
    assert 'day_key: row.querySelector("[data-segment-day]")?.value' in WORKSPACE_HTML
    assert 'start_time: row.querySelector("[data-segment-start]")?.value' in WORKSPACE_HTML
    assert 'end_time: row.querySelector("[data-segment-end]")?.value' in WORKSPACE_HTML
    assert 'function syncNoEventDateMirror' in WORKSPACE_HTML
    assert __version__ == main.DEPLOYMENT_VERSION == "0.54.4"
