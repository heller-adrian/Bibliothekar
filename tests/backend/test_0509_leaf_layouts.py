"""0.50.9: stable leaf identity, independent inputs, conservative matching."""
from __future__ import annotations
import sqlite3

import pytest
from app.event_leaf_layouts import leaf_descriptors, validate_leaf_choices
from app.event_structure_changes import _layout_from_paths
from app.event_layout import layout_paths


def _layout(paths):
    return _layout_from_paths(paths)


def test_0509_parent_child_and_day_own_distinct_input_folders():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE events (id TEXT, folder_name TEXT, parent_event_id TEXT)")
    db.executemany("INSERT INTO events VALUES (?,?,?)", [
        ("parent","Trip",None),
        ("child-1","Part A","parent"),
        ("child-2","Part B","parent"),
    ])
    descriptors=leaf_descriptors(db,{"id":"parent","preserve_day_folders":True},[
        "Part A/2026-07-20","Part B/2026-07-21",
    ])
    assert [d["leaf_key"] for d in descriptors]==[
        "child-1@2026-07-20","child-2@2026-07-21"
    ]
    layouts=[
        {**descriptors[0],"structure_enabled":True,"layout":_layout(["All","Sorted"]),"input_path":"All"},
        {**descriptors[1],"structure_enabled":True,"layout":_layout(["All","Export"]),"input_path":"All"},
    ]
    resolved=validate_leaf_choices(layouts,{
        "child-1@2026-07-20":"All",
        "child-2@2026-07-21":"All"
    },"")
    assert [x["input_path"] for x in resolved]==["All","All"]
    assert layout_paths(resolved[0]["layout"])!=layout_paths(resolved[1]["layout"])


def test_0509_unrecognized_leaf_key_rejected():
    layouts=[{"leaf_key":"a","structure_enabled":True,
              "layout":_layout(["All"]),"input_path":"All"}]
    with pytest.raises(ValueError,match="Unknown"):
        validate_leaf_choices(layouts,{"unknown":"All"},"")


def test_0509_invalid_input_folder_rejected():
    layouts=[{"leaf_key":"a","structure_enabled":True,
              "layout":_layout(["All","Sorted"]),"input_path":"All"}]
    with pytest.raises(ValueError):
        validate_leaf_choices(layouts,{"a":"Missing"},"")


def test_0509_parent_rename_does_not_change_identity():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE events (id TEXT, folder_name TEXT, parent_event_id TEXT)")
    db.execute("INSERT INTO events VALUES ('parent','Trip',NULL)")
    db.execute("INSERT INTO events VALUES ('child-id','Old Name','parent')")
    before=leaf_descriptors(db,{"id":"parent","preserve_day_folders":False},["Old Name"])
    db.execute("UPDATE events SET folder_name='New Name' WHERE id='child-id'")
    after=leaf_descriptors(db,{"id":"parent","preserve_day_folders":False},["New Name"])
    assert before[0]["leaf_key"]==after[0]["leaf_key"]=="child-id"


@pytest.mark.parametrize("value", [
    "/etc/passwd", "//shared/All", r"..\outside", "All/../Export",
    "All/./Export", "All//Export", "./All", "All/",
])
def test_0509_manual_structure_path_rejects_ambiguous_or_absolute(value):
    from app.event_structure_changes import EventStructureChangeError, _safe_rel
    with pytest.raises(EventStructureChangeError):
        _safe_rel(value)


def test_0509_manual_structure_path_accepts_valid_unicode_and_nested_relative():
    from app.event_structure_changes import _safe_rel
    assert _safe_rel("Sommer/Alle/A.JPG") == "Sommer/Alle/A.JPG"
    assert _safe_rel("2026/Skizzen – Δ") == "2026/Skizzen – Δ"
    assert _safe_rel("") == ""


def test_0509_staged_event_document_preserves_foreign_file(tmp_path):
    from app.event_structure_changes import (
        EventStructureChangeError, _write_prepared_document,
    )
    target=tmp_path/"Assign Later"/"2026"/"07-23 - Trip"/"event.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"source":"someone-else","event":{"id":"e"}}')
    original=target.read_bytes()
    with pytest.raises(EventStructureChangeError, match="anderen Ereignis"):
        _write_prepared_document(target,{"source":"kamera-automatisierung","event":{"id":"e"}})
    assert target.read_bytes()==original


def test_0509_staged_event_document_rejects_symlink_parent(tmp_path):
    from app.event_structure_changes import (
        EventStructureChangeError, _write_prepared_document,
    )
    import os
    stage=tmp_path/"Assign Later"/"2026"
    stage.mkdir(parents=True)
    outside=tmp_path/"external"
    outside.mkdir()
    (stage/"07-23 - Trip").symlink_to(outside, target_is_directory=True)
    target=stage/"07-23 - Trip"/"event.json"
    with pytest.raises(EventStructureChangeError, match="symbolischen Link"):
        _write_prepared_document(
            target, {"source":"kamera-automatisierung","event":{"id":"e"}}
        )
    assert not (outside/"event.json").exists()
