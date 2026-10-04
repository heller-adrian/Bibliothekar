"""0.40.1: mobile Import- und Ereignisansicht."""
from pathlib import Path

from app import main


def test_0401_version_contract():
    assert main.DEPLOYMENT_VERSION == "0.40.1"
    assert 'version="0.40.1"' in Path("app/source_helper.py").read_text(encoding="utf-8")
    assert '"version": "0.40.1"' in Path("app/source_helper.py").read_text(encoding="utf-8")
    assert "patch-0.40.1" in Path("compose.example.yaml").read_text(encoding="utf-8")
    assert "0.40.1 · Kamerakern 0.32.11" in Path("app/ui_shell.py").read_text(encoding="utf-8")


def test_0401_duplicate_paths_wrap_inside_import_card():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert 'class="duplicate-file-list"' in source
    assert ".duplicate-file-list code" in source
    assert "overflow-wrap:anywhere" in source
    assert "word-break:break-word" in source


def test_0401_no_event_segment_has_mobile_two_row_layout():
    source = Path("app/events_ui.py").read_text(encoding="utf-8")
    assert 'class="no-event-segment-fields"' in source
    assert "no-event-day-field" in source
    assert "no-event-start-field" in source
    assert "no-event-end-field" in source
    assert ".no-event-end-field {" in source
    assert "grid-column:1 / -1;" in source
    assert "grid-row:2;" in source


def test_0401_mobile_event_summary_is_three_compact_cards_in_one_row():
    source = Path("app/events_ui.py").read_text(encoding="utf-8")
    assert "section.summary {" in source
    assert "grid-template-columns:repeat(3,minmax(0,1fr));" in source
    assert "justify-content:space-between;" in source
    assert "text-align:right;" in source


def test_0401_mobile_event_actions_do_not_wrap():
    source = Path("app/events_ui.py").read_text(encoding="utf-8")
    assert ".event-card-actions {" in source
    assert "flex-wrap:nowrap;" in source
    assert ".event-card-actions > button" in source
    assert "font-size:clamp(.62rem,2.65vw,.78rem);" in source
    assert "white-space:nowrap;" in source
