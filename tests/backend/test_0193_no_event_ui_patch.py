from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION


def test_0193_version():
    assert APP_VERSION >= "0.19.3"


def test_workspace_no_event_helper_was_removed_in_favor_of_segments():
    assert 'id="no-event-range-generator"' not in WORKSPACE_HTML
    assert 'Zeitblock übernehmen' not in WORKSPACE_HTML
    assert 'id="no-event-segment-list"' in WORKSPACE_HTML
    assert 'existing-segment-static' in WORKSPACE_HTML


def test_events_no_event_editor_has_only_day_segments():
    assert 'edit-noevent-range-open' not in EVENTS_HTML
    assert 'Zeitspanne übernehmen' not in EVENTS_HTML
    assert 'Tagessegmente' in EVENTS_HTML
    assert '＋ Tagessegment hinzufügen' in EVENTS_HTML
