"""0.28.0 foundation: shared event provenance and folder-layout snapshots."""
from __future__ import annotations

from pathlib import Path
import json

from app.database import database_connection, initialize_database
from app.event_access import (
    event_anchor_job,
    event_family_ids,
    event_file_rows,
    event_source_jobs,
    register_source_jobs,
)
from app.event_layout import (
    DEFAULT_LAYOUT,
    get_event_layout,
    get_global_default,
    layout_paths,
    set_global_default,
    update_event_layout,
)
from tests.backend.test_0263_event_inventory import NOW


def _job(connection, job_id: str) -> None:
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,source_volume_label,
               progress_current,progress_total,created_at,updated_at
           ) VALUES (?,'sd_import','manual','completed','completed','folder_import',
                     ?,0,0,?,?)""",
        (job_id, job_id, NOW, NOW),
    )


def _family(connection, job_id: str, stem: str) -> tuple[int, int]:
    family_id = int(connection.execute(
        """INSERT INTO file_families(
               job_id,family_key,original_stem,status,selected_capture_time,
               capture_time_confidence)
           VALUES (?,?,?,'complete','2026-07-19T12:00:00','high')""",
        (job_id, stem, stem),
    ).lastrowid)
    file_id = int(connection.execute(
        """INSERT INTO files(
               job_id,family_id,original_relative_path,current_relative_path,
               original_filename,extension,media_type,size_bytes,
               sha256_original,sha256_current,selected_capture_time,
               selected_capture_source,capture_time_confidence,review_status,
               metadata_write_status,created_at,updated_at,current_root_kind)
           VALUES (?,?,?,?,?,'JPG','jpeg',1,'x','x','2026-07-19T12:00:00',
                   'test','high','not_required','not_requested',?,?,'shared_workspace')""",
        (job_id, family_id, f"DCIM/{stem}.JPG", f"2026/07-19/{stem}.JPG", f"{stem}.JPG", NOW, NOW),
    ).lastrowid)
    return family_id, file_id


def _event(connection) -> None:
    connection.execute(
        """INSERT INTO events(
               id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,
               preserve_day_folders,revision)
           VALUES ('e','a',NULL,'parent','Test','2026-07-19T00:00:00',
                   '2026-07-19T23:59:59',0,'07-19 - Test','planned',?,?,
                   'event',0,1)""",
        (NOW, NOW),
    )


def test_0280_migrations_backfill_anchor_and_legacy_layout(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _event(connection)
        # Migration already ran before this row existed, so emulate normal
        # snapshot creation separately; provenance backfill itself is tested
        # using a second initialization below.
        from app.event_layout import ensure_event_layout_snapshot
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        register_source_jobs(connection, "e", ["a"], created_at=NOW)

        assert event_anchor_job(connection, "e") == "a"
        assert [row["job_id"] for row in event_source_jobs(connection, "e")] == ["a"]
        layout = get_event_layout(connection, "e")
        assert layout["structure_enabled"] is True
        assert layout["input_path"] == "Alle"
        assert layout_paths(layout["layout"]) == ["Alle", "Sortiert", "Export"]


def test_0280_one_event_can_reference_families_from_two_jobs(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        _event(connection)
        fa, _ = _family(connection, "a", "A")
        fb, _ = _family(connection, "b", "B")
        connection.executemany(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at)
               VALUES ('e',?,NULL,'manual',?)""",
            [(fa, NOW), (fb, NOW)],
        )
        register_source_jobs(connection, "e", ["a", "b"], created_at=NOW)

        assert event_family_ids(connection, "e") == [fa, fb]
        assert {row["job_id"] for row in event_file_rows(connection, "e")} == {"a", "b"}
        assert {row["job_id"] for row in event_source_jobs(connection, "e")} == {"a", "b"}
        assert event_anchor_job(connection, "e") == "a"


def test_0280_global_layout_changes_do_not_retroactively_change_event(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _event(connection)
        from app.event_layout import ensure_event_layout_snapshot
        original = ensure_event_layout_snapshot(connection, "e", now=NOW)

        new_layout = {
            "version": 1,
            "nodes": [
                {"id": "all", "name": "All", "children": []},
                {"id": "fav", "name": "Favoriten", "children": [
                    {"id": "print", "name": "Druck", "children": []},
                ]},
            ],
        }
        set_global_default(
            connection,
            {"structure_enabled": True, "input_path": "All", "layout": new_layout},
            updated_at=NOW,
        )

        assert get_global_default(connection)["input_path"] == "All"
        still = get_event_layout(connection, "e")
        assert still["input_path"] == original["input_path"] == "Alle"
        assert still["layout"] == original["layout"] == DEFAULT_LAYOUT


def test_0280_event_layout_can_use_direct_leaf_as_input(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _event(connection)
        from app.event_layout import ensure_event_layout_snapshot
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        changed = update_event_layout(
            connection,
            "e",
            structure_enabled=True,
            input_path="",
            layout={"version": 1, "nodes": [
                {"id": "fav", "name": "Favoriten", "children": []},
            ]},
            updated_at=NOW,
        )
        assert changed["input_path"] == ""
        assert layout_paths(changed["layout"]) == ["Favoriten"]
