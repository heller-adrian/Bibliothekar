from app.main import APP_VERSION
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def test_0203_version():
    assert APP_VERSION == "0.27.1"


def test_no_event_continuation_uses_only_day_segments_and_locks_existing():
    assert "renderNoEventRangeGeneratorFields" not in WORKSPACE_HTML
    assert 'existing-segment-static' in WORKSPACE_HTML
    assert "_locked:true,_existing:true" in WORKSPACE_HTML
    assert "Zeitblock hinzufügen" not in WORKSPACE_HTML

def test_reassignment_is_compact_by_day_without_family_drilldown():
    # 0.25 removes the target selector: assignment happens through workspace cards.
    assert 'In Aufnahmen öffnen' in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert 'id="reassignment-apply"' not in EVENTS_HTML
    assert 'segment.start_time' in EVENTS_HTML and 'segment.end_time' in EVENTS_HTML
    assert 'segment.family_count' in EVENTS_HTML and 'segment.file_count' in EVENTS_HTML


def test_existing_no_event_segments_are_not_editable_in_continue_dialog():
    assert "data-existing-range" not in EVENTS_HTML
    assert "Zeitblock übernehmen" not in EVENTS_HTML
    assert 'id="add-no-event-segment"' in EVENTS_HTML
