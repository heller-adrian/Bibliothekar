"""0.28.0: safe normalization of DB-only legacy multi-backup extensions."""
from __future__ import annotations

from pathlib import Path

from app.database import database_connection, initialize_database
from app.legacy_multi_backup import normalize_unapplied_legacy_extensions
from tests.backend.test_0263_event_inventory import NOW


def _job(connection, job_id: str) -> None:
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,source_volume_label,
               created_at,updated_at
           ) VALUES (?,'sd_import','manual','completed','completed',
                     'folder_import',?,?,?)""",
        (job_id, job_id, NOW, NOW),
    )


def _event(
    connection,
    event_id: str,
    job_id: str,
    *,
    name: str,
    status: str = "planned",
    parent_event_id: str | None = None,
    event_level: str = "parent",
    start: str = "2026-07-19T00:00:00",
    end: str = "2026-07-19T23:59:59",
    event_kind: str = "event",
    linked_event_id: str | None = None,
    linkage_kind: str | None = None,
) -> None:
    connection.execute(
        """INSERT INTO events(
               id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,
               preserve_day_folders,revision,linked_event_id,linkage_kind,
               time_model_version,timeline_model
           ) VALUES (?,?,?,?,?,?,?,0,?,?,?,?,?,0,1,?,?,2,?)""",
        (
            event_id,
            job_id,
            parent_event_id,
            event_level,
            name,
            start,
            end,
            ("07-19 - " + name) if event_level == "parent" else name,
            status,
            NOW,
            NOW,
            event_kind,
            linked_event_id,
            linkage_kind,
            "segments" if event_kind == "no_event" else "continuous",
        ),
    )


def _family(
    connection,
    job_id: str,
    family_key: str,
    capture: str,
    current_path: str,
) -> int:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, family_key, family_key, capture),
        ).lastrowid
    )
    connection.execute(
        """INSERT INTO files(
               job_id,family_id,original_relative_path,current_relative_path,
               original_filename,extension,media_type,size_bytes,
               sha256_original,sha256_current,selected_capture_time,
               selected_capture_source,capture_time_confidence,review_status,
               metadata_write_status,created_at,updated_at,current_root_kind
           ) VALUES (?,?,?,?,?,'JPG','jpeg',1,'x','x',?,
                     'test','high','not_required','not_requested',?,?,
                     'shared_workspace')""",
        (
            job_id,
            family_id,
            "DCIM/" + family_key + ".JPG",
            current_path,
            family_key + ".JPG",
            capture,
            NOW,
            NOW,
        ),
    )
    return family_id


def test_0280_db_only_planned_extension_merges_into_canonical_child(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        _event(connection, "target", "a", name="Reise")
        _event(
            connection,
            "morning",
            "a",
            name="Morgen",
            parent_event_id="target",
            event_level="child",
            start="2026-07-19T08:00:00",
            end="2026-07-19T11:59:59",
        )
        _event(
            connection,
            "legacy",
            "b",
            name="Ergänzung: Reise",
            linked_event_id="target",
            linkage_kind="planned_extension",
        )
        _event(
            connection,
            "legacy_morning",
            "b",
            name="Morgen",
            parent_event_id="legacy",
            event_level="child",
            start="2026-07-19T08:00:00",
            end="2026-07-19T11:59:59",
        )
        family_id = _family(
            connection,
            "b",
            "B",
            "2026-07-19T10:00:00",
            "2026/incoming/B.JPG",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('legacy_morning',?,NULL,'manual',?)""",
            (family_id, NOW),
        )

    result = normalize_unapplied_legacy_extensions(db)
    assert result["merged_count"] == 1
    assert result["merged"][0]["legacy_event_id"] == "legacy"
    assert result["merged"][0]["target_event_id"] == "target"

    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='legacy'"
        ).fetchone()[0] == 0
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()
        sources = connection.execute(
            "SELECT job_id FROM event_source_jobs WHERE event_id='target' ORDER BY job_id"
        ).fetchall()
    assert assignment["event_id"] == "morning"
    assert [row["job_id"] for row in sources] == ["a", "b"]


def test_0280_db_only_no_event_extension_merges_segments(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        _event(
            connection,
            "target",
            "a",
            name="Ohne Ereignis",
            start="2026-07-15T08:00:00",
            end="2026-07-15T12:00:59",
            event_kind="no_event",
        )
        _event(
            connection,
            "legacy",
            "b",
            name="Ohne Ereignis",
            start="2026-07-24T09:00:00",
            end="2026-07-24T11:00:59",
            event_kind="no_event",
            linked_event_id="target",
            linkage_kind="planned_extension",
        )
        connection.executemany(
            """INSERT INTO event_time_segments(
                   event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,
                   source,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    "target","a","2026-07-15","08:00","12:00",
                    "2026-07-15T08:00:00","2026-07-15T12:00:59",
                    "user",NOW,NOW,
                ),
                (
                    "legacy","b","2026-07-24","09:00","11:00",
                    "2026-07-24T09:00:00","2026-07-24T11:00:59",
                    "user",NOW,NOW,
                ),
            ],
        )
        family_id = _family(
            connection,
            "b",
            "B",
            "2026-07-24T10:00:00",
            "2026/incoming/B.JPG",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('legacy',?,NULL,'manual',?)""",
            (family_id, NOW),
        )

    result = normalize_unapplied_legacy_extensions(db)
    assert result["merged_count"] == 1

    with database_connection(db) as connection:
        segments = connection.execute(
            """SELECT day_key,start_time,end_time
               FROM event_time_segments
               WHERE event_id='target'
               ORDER BY day_key,start_time"""
        ).fetchall()
        target = connection.execute(
            "SELECT start_datetime,end_datetime FROM events WHERE id='target'"
        ).fetchone()
    assert [tuple(row) for row in segments] == [
        ("2026-07-15","08:00","12:00"),
        ("2026-07-24","09:00","11:00"),
    ]
    assert tuple(target) == (
        "2026-07-15T08:00:00",
        "2026-07-24T11:00:59",
    )


def test_0280_physical_legacy_extension_is_never_auto_merged(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        _event(connection, "target", "a", name="Reise")
        _event(
            connection,
            "legacy",
            "b",
            name="Ergänzung: Reise",
            linked_event_id="target",
            linkage_kind="planned_extension",
        )
        family_id = _family(
            connection,
            "b",
            "B",
            "2026-07-19T10:00:00",
            "2026/Ergänzungen/07-19 - Reise - b/B.JPG",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('legacy',?,NULL,'manual',?)""",
            (family_id, NOW),
        )

    result = normalize_unapplied_legacy_extensions(db)
    assert result["merged_count"] == 0
    assert result["skipped"] == ["legacy"]

    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='legacy'"
        ).fetchone()[0] == 1
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()
    assert assignment["event_id"] == "legacy"
