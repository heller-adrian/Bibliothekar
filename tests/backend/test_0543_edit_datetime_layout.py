"""0.55.0: Edit-only date/time pairs, vertical centering and iOS overflow safety."""
from __future__ import annotations
import re

from app import __version__, main
from app.events_ui import EVENTS_HTML


def _css() -> str:
    return EVENTS_HTML.split("<style>", 1)[1].split("</style>", 1)[0]


def test_0543_editor_pairs_override_stacked_mobile_rules():
    css = _css()
    pair = re.search(
        r'#event-edit-dialog \.edit-boundary,\s*'
        r'#event-edit-dialog \.child-segment-boundary\s*\{([^}]+)\}',
        css, re.S,
    )
    assert pair is not None
    rules = re.sub(r'\s+', '', pair.group(1)).lower()
    assert 'display:grid;' in rules
    assert 'grid-template-columns:minmax(0,3fr)minmax(0,2fr)!important;' in rules
    assert 'gap:8px;' in rules
    assert css.index('@container event-editor (max-width:720px)') < pair.start()
    # An ID-scoped !important rule wins over older single-column
    # @media/@container declarations also using !important.
    assert '#event-edit-dialog .edit-boundary' in pair.group(0)
    assert '#event-edit-dialog .child-segment-boundary' in pair.group(0)


def test_0543_parent_existing_and_new_subevents_use_same_grid_classes():
    assert '<div class="edit-boundary">' in EVENTS_HTML
    assert EVENTS_HTML.count('<div class="child-segment-boundary">') >= 4
    assert 'data-child-start-time type="time"' in EVENTS_HTML
    assert 'data-child-end-time type="time"' in EVENTS_HTML
    assert 'id="edit-start-date" type="date"' in EVENTS_HTML
    assert 'id="edit-end-time" type="time"' in EVENTS_HTML


def test_0543_center_native_date_and_time_while_preserving_0542_fix():
    css = _css()
    input_rule = re.search(
        r'#event-edit-dialog input\[type="date"\],\s*'
        r'#event-edit-dialog input\[type="time"\]\s*\{([^}]+)\}',
        css, re.S
    )
    assert input_rule is not None
    old = re.sub(r'\s+', '', input_rule.group(1)).lower()
    for rule in (
        '-webkit-appearance:none!important;',
        'appearance:none!important;',
        'padding:0!important;',
        'width:calc(100%-2px)!important;',
        'box-sizing:border-box!important;'
    ):
        assert rule in old
    centers = re.findall(
        r'#event-edit-dialog input\[type="date"\],\s*'
        r'#event-edit-dialog input\[type="time"\]\s*\{([^}]+)\}',
        css, re.S,
    )
    assert len(centers) == 2
    vertical = re.sub(r'\s+', '', centers[1]).lower()
    assert 'block-size:48px!important;' in vertical
    assert 'line-height:48px!important;' in vertical
    pseudo = css[css.index('::-webkit-date-and-time-value', css.index('/* 0.54.3:')):]
    assert '::-webkit-datetime-edit' in pseudo
    assert 'align-items:center;' in pseudo
    assert 'justify-content:center;' in pseudo
    assert 'padding:0;' in pseudo
    assert __version__ == main.DEPLOYMENT_VERSION == '0.55.0'
