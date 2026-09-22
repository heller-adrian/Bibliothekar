from app.main import APP_VERSION
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def test_0203_version():
    assert APP_VERSION == "0.25.1"


def test_no_event_range_generator_locks_existing_month():
    assert "renderNoEventRangeGeneratorFields" in WORKSPACE_HTML
    assert "data-fixed-range-start-day" in WORKSPACE_HTML
    assert "data-fixed-range-end-day" in WORKSPACE_HTML
    assert "Monat/Jahr" in WORKSPACE_HTML


def test_reassignment_is_compact_by_day_without_family_drilldown():
    # 0.25 removes the target selector: assignment happens through workspace cards.
    assert 'In Aufnahmen öffnen' in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert 'id="reassignment-apply"' not in EVENTS_HTML
    assert 'segment.start_time' in EVENTS_HTML and 'segment.end_time' in EVENTS_HTML
    assert 'segment.family_count' in EVENTS_HTML and 'segment.file_count' in EVENTS_HTML


def test_existing_no_event_time_blocks_are_editable():
    assert "data-existing-range" in EVENTS_HTML
    assert "data-edit-range-start-day" in EVENTS_HTML
    assert "data-edit-range-end-day" in EVENTS_HTML
    assert "data-apply-existing-range" in EVENTS_HTML
    assert "Zeitblock übernehmen" in EVENTS_HTML

