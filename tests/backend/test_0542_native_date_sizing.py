"""0.55.0: Native iOS date/time overflow regression on event edit dialog.

WKWebKit may retain content-box sizing on native date/time inputs.
The optional real-browser geometry smoke test was run separately; these
contract tests ensure that the CSS mitigation stays scoped and intact.
"""
from __future__ import annotations

import re

from app.events_ui import EVENTS_HTML


def _native_date_time_block() -> tuple[str, str]:
    source = EVENTS_HTML.split("<style>", 1)[1].split("</style>", 1)[0]
    pattern = re.compile(
        r'#event-edit-dialog input\[type="date"\]\s*,\s*'
        r'#event-edit-dialog input\[type="time"\]\s*\{([^}]+)\}',
        re.S,
    )
    # 0.54.3 adds a second, later rule solely for vertical centering.
    # Assert the original 0.54.2 native overflow mitigation remains intact.
    section = source.split("/* 0.54.2:", 1)[1].split("/* 0.54.3:", 1)[0]
    matches = list(pattern.finditer(section))
    assert len(matches) == 1, "Exactly one original 0.54.2 overflow reset is required"
    return source, matches[0].group(1)


def test_0542_edit_date_and_time_are_contained_even_under_content_box():
    source, block = _native_date_time_block()
    normalized = re.sub(r"\s+", "", block).lower()
    for expected in (
        "-webkit-appearance:none!important;",
        "appearance:none!important;",
        "box-sizing:border-box!important;",
        "padding:0!important;",
        "inline-size:calc(100%-2px)!important;",
        "width:calc(100%-2px)!important;",
        "min-inline-size:0!important;",
        "max-inline-size:100%!important;",
    ):
        assert expected in normalized, expected
    # The iOS native-form-control override comes after the previous
    # broad 0.54.1 edit-input sizing rule (cascade order matters).
    assert source.index("#event-edit-dialog .edit-field > input") < source.index(
        '#event-edit-dialog input[type="date"]'
    )


def test_0542_parent_child_and_dynamically_added_subevents_keep_native_pickers():
    # The fix targets types, not specific IDs, so newly created child rows
    # have identical protection without extra JavaScript or data migration.
    assert '<input id="edit-start-date" type="date"' in EVENTS_HTML
    assert '<input id="edit-end-time" type="time"' in EVENTS_HTML
    assert 'data-child-start-date","data-child-start-month-year"' in EVENTS_HTML
    assert 'data-child-start-time type="time"' in EVENTS_HTML
    assert 'data-child-end-time type="time"' in EVENTS_HTML
    assert 'row.innerHTML=' in EVENTS_HTML
    source, _ = _native_date_time_block()
    assert "#event-edit-dialog input[type=\"text\"]" not in source
