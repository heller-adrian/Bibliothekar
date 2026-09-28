import sqlite3

from app.event_structure import assigned_day_keys_by_event
from app.structure_view import render_structure


def test_02611_read_only_structure_keeps_parent_and_child_days_separate():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            parent_event_id TEXT
        );
        CREATE TABLE file_families (
            id INTEGER PRIMARY KEY,
            selected_capture_time TEXT
        );
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            family_id INTEGER
        );
        CREATE TABLE event_assignments (
            event_id TEXT,
            family_id INTEGER,
            file_id INTEGER
        );

        INSERT INTO events(id,parent_event_id) VALUES
            ('parent',NULL),
            ('child','parent');

        INSERT INTO file_families(id,selected_capture_time) VALUES
            (1,'2026-07-20T13:11:13'),
            (2,'2026-07-21T17:28:08');

        INSERT INTO event_assignments(event_id,family_id,file_id) VALUES
            ('child',1,NULL),
            ('parent',2,NULL);
        """
    )

    days = assigned_day_keys_by_event(connection, "parent")
    assert days == {
        "child": ["2026-07-20"],
        "parent": ["2026-07-21"],
    }

    text = "\n".join(
        render_structure(
            "2026",
            "07-20 - Test",
            days["parent"],
            [{"folder_name": "Test 2", "day_keys": days["child"]}],
            True,
        )
    )

    before_child, child = text.split("Test 2", 1)
    assert "2026-07-21" in before_child
    assert "2026-07-20" in child
    assert "2026-07-21" not in child


def test_02611_read_only_structure_supports_direct_file_assignments():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            parent_event_id TEXT
        );
        CREATE TABLE file_families (
            id INTEGER PRIMARY KEY,
            selected_capture_time TEXT
        );
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            family_id INTEGER
        );
        CREATE TABLE event_assignments (
            event_id TEXT,
            family_id INTEGER,
            file_id INTEGER
        );

        INSERT INTO events(id,parent_event_id) VALUES
            ('parent',NULL),
            ('child','parent');
        INSERT INTO file_families(id,selected_capture_time)
            VALUES (7,'2026-07-20T14:10:20');
        INSERT INTO files(id,family_id) VALUES (70,7);
        INSERT INTO event_assignments(event_id,family_id,file_id)
            VALUES ('child',NULL,70);
        """
    )

    assert assigned_day_keys_by_event(connection, "parent") == {
        "child": ["2026-07-20"],
    }
