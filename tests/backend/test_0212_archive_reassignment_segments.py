import sqlite3

import pytest

from app.archive_reassignment_segments import (
    ArchiveSegmentError,
    build_archive_reassignment_segments,
    validate_atomic_segment_selection,
)
from app.events_ui import EVENTS_HTML


def _connection():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            parent_event_id TEXT,
            event_kind TEXT NOT NULL,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL
        );
        CREATE TABLE event_assignments (
            event_id TEXT NOT NULL,
            family_id INTEGER NOT NULL
        );
        CREATE TABLE event_time_segments (
            event_id TEXT NOT NULL,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL
        );
        """
    )
    return c


def test_archived_child_shrink_releases_exact_structure_range_not_capture_minmax():
    c = _connection()
    c.execute(
        "INSERT INTO events VALUES ('parent',NULL,'event','2026-07-15T00:00:00','2026-07-15T23:59:59')"
    )
    c.execute(
        "INSERT INTO events VALUES ('child','parent','event','2026-07-15T08:00:00','2026-07-15T18:00:59')"
    )
    c.executemany(
        "INSERT INTO event_assignments VALUES ('child',?)",
        [(1,), (2,)],
    )
    cr = {
        "event_id": "parent",
        "event_kind": "event",
        "start_date": "2026-07-15",
        "end_date": "2026-07-15",
        "uses_time_range": 0,
        "child_segments_json": '[{"id":"child","name":"Tag","start_time":"08:00","end_time":"11:59"}]',
        "no_event_segments": "[]",
    }
    pending = [
        {"family_id": 1, "selected_capture_time": "2026-07-15T14:10:00", "file_count": 2},
        {"family_id": 2, "selected_capture_time": "2026-07-15T17:55:00", "file_count": 2},
    ]

    segments = build_archive_reassignment_segments(c, cr, pending)

    assert len(segments) == 1
    assert segments[0]["start_datetime"] == "2026-07-15T12:00:00"
    assert segments[0]["end_datetime"] == "2026-07-15T18:00:59"
    assert segments[0]["family_ids"] == [1, 2]
    assert segments[0]["family_count"] == 2
    assert segments[0]["file_count"] == 4


def test_archived_multiday_release_is_split_at_calendar_day_boundaries():
    c = _connection()
    c.execute(
        "INSERT INTO events VALUES ('parent',NULL,'event','2026-07-23T00:00:00','2026-07-24T23:59:59')"
    )
    c.executemany(
        "INSERT INTO event_assignments VALUES ('parent',?)",
        [(1,), (2,)],
    )
    cr = {
        "event_id": "parent",
        "event_kind": "event",
        "start_date": "2026-07-23",
        "end_date": "2026-07-23",
        "uses_time_range": 1,
        "start_time": "00:00",
        "end_time": "20:00",
        "child_segments_json": "[]",
        "no_event_segments": "[]",
    }
    pending = [
        {"family_id": 1, "selected_capture_time": "2026-07-23T21:30:00", "file_count": 2},
        {"family_id": 2, "selected_capture_time": "2026-07-24T12:00:00", "file_count": 2},
    ]

    segments = build_archive_reassignment_segments(c, cr, pending)

    assert [
        (s["day_key"], s["start_time"], s["end_time"], s["family_ids"])
        for s in segments
    ] == [
        ("2026-07-23", "20:01", "23:59", [1]),
        ("2026-07-24", "00:00", "23:59", [2]),
    ]


def test_archived_reassignment_rejects_family_subset_of_one_released_segment():
    segments = [{
        "day_key": "2026-07-15",
        "start_time": "12:00",
        "end_time": "18:00",
        "start_datetime": "2026-07-15T12:00:00",
        "end_datetime": "2026-07-15T18:00:59",
        "family_ids": [1, 2],
    }]

    with pytest.raises(ArchiveSegmentError, match="vollständige Tages-/Zeitsegmente"):
        validate_atomic_segment_selection(segments, [1])

    selected = validate_atomic_segment_selection(segments, [1, 2])
    assert selected[0]["family_ids"] == [1, 2]


def test_archived_no_event_releases_exact_stored_segment_remainder():
    c = _connection()
    c.execute(
        "INSERT INTO events VALUES ('noevent',NULL,'no_event','2026-07-15T08:00:00','2026-07-15T18:00:59')"
    )
    c.execute(
        "INSERT INTO event_time_segments VALUES ('noevent','2026-07-15T08:00:00','2026-07-15T18:00:59')"
    )
    cr = {
        "event_id": "noevent",
        "event_kind": "no_event",
        "start_date": "2026-07-15",
        "end_date": "2026-07-15",
        "uses_time_range": 0,
        "child_segments_json": "[]",
        "no_event_segments": '[{"day_key":"2026-07-15","start_time":"08:00","end_time":"11:59"}]',
    }
    pending = [{"family_id": 3, "selected_capture_time": "2026-07-15T17:30:00", "file_count": 2}]

    segments = build_archive_reassignment_segments(c, cr, pending)

    assert [(s["start_datetime"], s["end_datetime"]) for s in segments] == [
        ("2026-07-15T12:00:00", "2026-07-15T18:00:59")
    ]


def test_archive_ui_returns_released_segments_to_ssd_before_finder_work():
    assert "data-archive-reassign-segment" not in EVENTS_HTML
    assert "data-archive-reassign-target" not in EVENTS_HTML
    assert "Ausgewählte Segmente zuordnen" not in EVENTS_HTML
    assert "Freigewordene Archivdateien im Arbeitsbereich sichern" in EVENTS_HTML
    assert "Arbeitsbereich-Kopien prüfen" in EVENTS_HTML
    assert "Bestätigte Archivoriginale entfernen" in EVENTS_HTML
    assert "Entfernung aus dem Archiv prüfen" in EVENTS_HTML
    assert "/release-copy/verify" in EVENTS_HTML
    assert "/release-removal/verify" in EVENTS_HTML

