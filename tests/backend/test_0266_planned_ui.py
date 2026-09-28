from pathlib import Path

from app.main import APP_VERSION
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.ui_shell import BIBLIOTHEKAR_JS


ROOT = Path(__file__).resolve().parents[2]


def test_0266_version():
    assert APP_VERSION == "0.27.3"


def test_0266_workspace_removes_duplicate_saved_events_and_noevent_range_helper():
    assert 'id="saved-events-section"' not in WORKSPACE_HTML
    assert "Gespeicherte Ereignisse" not in WORKSPACE_HTML
    assert 'id="no-event-range-details"' not in WORKSPACE_HTML
    assert "Zeitspanne · Auswahlhilfe" not in WORKSPACE_HTML
    assert "Zeitblock hinzufügen" not in WORKSPACE_HTML
    assert 'id="no-event-segment-list"' in WORKSPACE_HTML


def test_0266_existing_noevent_segments_are_read_only_when_continuing():
    assert "existing-segment-static" in WORKSPACE_HTML
    assert "_locked:true,_existing:true" in WORKSPACE_HTML
    assert "· BESTEHEND" in WORKSPACE_HTML


def test_0266_event_creation_uses_real_subevents_and_paired_boundaries():
    assert 'id="event-start-time-label"' in WORKSPACE_HTML
    assert 'id="event-end-time-label"' in WORKSPACE_HTML
    assert 'id="add-create-subevent"' in WORKSPACE_HTML
    assert 'data-create-child-start-date' in WORKSPACE_HTML
    assert 'data-create-child-end-time' in WORKSPACE_HTML
    assert "collectCreateSubevents()" in WORKSPACE_HTML
    assert "subevents:" in WORKSPACE_HTML
    assert 'id="child-event-name"' not in WORKSPACE_HTML
    assert 'class="create-subevent-top"' in WORKSPACE_HTML
    assert 'class="create-subevent-boundaries"' in WORKSPACE_HTML
    assert "Unterereignisse organisieren Teilzeiträume" not in WORKSPACE_HTML


def test_0266_noevent_preview_is_complex_and_workspace_controls_can_dock():
    assert "Datenbank-Zeitraum:</strong> mehrere gespeicherte Zeitsegmente" in WORKSPACE_HTML
    assert 'id="selection-bar-anchor"' in WORKSPACE_HTML
    assert "selection-bar.is-header-docked" in WORKSPACE_HTML
    assert "is-scroll-floating" not in WORKSPACE_HTML
    assert "selectionDockTarget.appendChild(selectionBar)" in WORKSPACE_HTML
    assert "min-width:821px" in WORKSPACE_HTML
    assert "--bk-shell-sticky-height" in BIBLIOTHEKAR_JS


def test_0266_inspector_pages_large_noevent_and_collapses_family_days():
    assert 'id="inspect-segment-host"' in EVENTS_HTML
    assert 'id="inspect-more-segments"' in EVENTS_HTML
    assert "segmentLimit=10" in EVENTS_HTML
    assert 'id="inspect-family-days"' in EVENTS_HTML
    assert 'id="inspect-more-family-days"' in EVENTS_HTML
    assert "familyDayLimit=10" in EVENTS_HTML
    assert "<strong>komplex</strong>" in EVENTS_HTML


def test_0266_edit_errors_stay_inside_modal():
    assert 'id="event-edit-inline-error"' in EVENTS_HTML
    assert "function showEventEditError" in EVENTS_HTML
    assert "saveEventEditor().catch(error => showEventEditError(error.message))" in EVENTS_HTML


def test_0266_noevent_editor_has_only_segments():
    assert "Zeitspanne · nur Auswahlhilfe" not in EVENTS_HTML
    assert "Zeitspanne ergänzen" not in EVENTS_HTML
    assert "Zeitspanne übernehmen" not in EVENTS_HTML
    assert 'id="add-no-event-segment"' in EVENTS_HTML
