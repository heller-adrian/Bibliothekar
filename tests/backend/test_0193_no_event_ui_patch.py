from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION


def test_0193_version():
    assert APP_VERSION >= "0.19.3"


def test_workspace_timeblock_generator_requires_explicit_apply():
    assert 'id="no-event-range-generator" hidden' in WORKSPACE_HTML
    assert 'id="apply-no-event-range-block"' in WORKSPACE_HTML
    assert 'Zeitblock übernehmen' in WORKSPACE_HTML
    assert 'id="cancel-no-event-range-block"' in WORKSPACE_HTML


def test_events_no_event_range_helper_and_compact_segment_layout():
    assert 'id="edit-noevent-range-open"' in EVENTS_HTML
    assert '＋ Zeitspanne ergänzen' in EVENTS_HTML
    assert 'id="edit-noevent-range-panel" hidden' in EVENTS_HTML
    assert 'Zeitspanne übernehmen' in EVENTS_HTML
    assert 'grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px' in EVENTS_HTML
