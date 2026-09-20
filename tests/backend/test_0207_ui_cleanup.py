from app.main import APP_VERSION
from app.events_ui import EVENTS_HTML


def test_0207_version():
    assert APP_VERSION == "0.24.1"


def test_reassignment_warning_is_spaced_from_event_details():
    assert ".reassignment-resume + .event-details { margin-top:10px; }" in EVENTS_HTML
    assert ".reassignment-resume + .event-details > summary" in EVENTS_HTML
    assert "Änderung verwerfen" in EVENTS_HTML
    assert "In Sortieren öffnen" in EVENTS_HTML
