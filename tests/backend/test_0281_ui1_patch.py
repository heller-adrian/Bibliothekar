"""Regression tests for the 0.28.1-ui1 deep-test intermediate patch."""
from pathlib import Path

import pytest

from app.event_structure_changes import (
    EventStructureChangeError,
    _validated_structure_input,
)


def _layout():
    return {
        "version": 1,
        "nodes": [
            {"id": "all", "name": "Alle", "children": []},
            {"id": "sorted", "name": "Sortiert", "children": []},
        ],
    }


def test_ui1_active_structure_requires_existing_input_folder():
    detected = {"proposed_structure_enabled": True}

    with pytest.raises(EventStructureChangeError, match="Input-Ordner"):
        _validated_structure_input(detected, _layout(), "")

    with pytest.raises(EventStructureChangeError, match="gehört nicht"):
        _validated_structure_input(detected, _layout(), "Nicht vorhanden")

    enabled, selected = _validated_structure_input(detected, _layout(), "Alle")
    assert enabled is True
    assert selected == "Alle"


def test_ui1_structure_off_canonicalises_input_to_event_root():
    enabled, selected = _validated_structure_input(
        {"proposed_structure_enabled": False},
        _layout(),
        "Alle",
    )
    assert enabled is False
    assert selected == ""


def test_ui1_manual_change_ui_is_compact_and_durable():
    source = Path("app/events_ui.py").read_text(encoding="utf-8")

    assert "bk0511EventLabel(\"Ordneränderungen\",\"Folder changes\")} · ${folderChangeCount}" in source
    assert "bk0511EventLabel(\"Dateiänderungen\",\"File changes\")} · ${moves.length}" in source
    assert "Bereits in der vorbereiteten event.json gespeichert." in source
    assert "clearStructureTaskFromUrl(changeId)" in source
    assert 'if(change.status==="completed")' in source
    assert "await refreshGlobalTasks();" in source


def test_ui1_event_suggestion_card_aligns_with_workspace():
    source = Path("app/workspace_ui.py").read_text(encoding="utf-8")
    assert ".suggestions-panel { margin:0 0 18px; width:100%; box-sizing:border-box;" in source
