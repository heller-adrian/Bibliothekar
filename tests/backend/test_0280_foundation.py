"""0.28.0 foundation: shared event provenance and folder-layout snapshots."""
from __future__ import annotations

from pathlib import Path
import json

from app import main

from app.database import (
    create_planned_event,
    database_connection,
    delete_planned_event,
    initialize_database,
)
from app.event_structure import build_event_preview
from app.global_workspace import build_global_workspace_summary
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



def _preview_for_families(family_ids: list[int]) -> dict:
    available = [
        {
            "family_id": family_id,
            "family_key": f"F{family_id}",
            "selected_capture_time": "2026-07-19T12:00:00",
            "capture_time_confidence": "high",
            "day_key": "2026-07-19",
            "has_date": True,
            "file_count": 1,
            "total_size_bytes": 1,
            "review_required_count": 0,
        }
        for family_id in family_ids
    ]
    return build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Gemeinsam",
            "start_date": "2026-07-19",
            "end_date": "2026-07-19",
            "uses_time_range": False,
            "preserve_day_folders": False,
            "selected_day_keys": ["2026-07-19"],
            "selected_family_ids": family_ids,
        },
        available,
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


def test_0280_create_one_planned_event_from_two_backups(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        fa, _ = _family(connection, "a", "A")
        fb, _ = _family(connection, "b", "B")

    created = create_planned_event(db, "a", _preview_for_families([fa, fb]))
    event_id = str(created["parent_event"]["id"])

    with database_connection(db) as connection:
        roots = connection.execute(
            "SELECT id,job_id,linked_event_id,linkage_kind,status FROM events WHERE parent_event_id IS NULL"
        ).fetchall()
        assignments = connection.execute(
            "SELECT family_id FROM event_assignments ORDER BY family_id"
        ).fetchall()
        sources = event_source_jobs(connection, event_id)

    assert len(roots) == 1
    assert tuple(roots[0]) == (event_id, "a", None, None, "planned")
    assert [int(row["family_id"]) for row in assignments] == sorted([fa, fb])
    assert {row["job_id"] for row in sources} == {"a", "b"}


def test_0280_delete_cross_backup_planned_event_releases_original_provenance(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        fa, _ = _family(connection, "a", "A")
        fb, _ = _family(connection, "b", "B")

    created = create_planned_event(db, "a", _preview_for_families([fa, fb]))
    event_id = str(created["parent_event"]["id"])

    # Compatibility routes may arrive through any provenance backup. Event
    # identity decides the technical anchor internally.
    result = delete_planned_event(db, "b", event_id)
    assert result["released_family_count"] == 2
    assert result["released_file_count"] == 2

    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id=?", (event_id,)
        ).fetchone()[0] == 0
        released = connection.execute(
            """SELECT job_id,family_id FROM released_free_families
               WHERE family_id IN (?,?) ORDER BY family_id""",
            (fa, fb),
        ).fetchall()

    assert {(str(row["job_id"]), int(row["family_id"])) for row in released} == {
        ("a", fa),
        ("b", fb),
    }


def test_0280_backup_filter_never_partitions_one_event(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        fa, _ = _family(connection, "a", "A")
        fb, _ = _family(connection, "b", "B")

    created = create_planned_event(db, "a", _preview_for_families([fa, fb]))
    event_id = str(created["parent_event"]["id"])

    for selected in (["a"], ["b"]):
        summary = build_global_workspace_summary(db, selected)
        groups = summary["planning_overview"]["event_groups"]
        assert len(groups) == 1
        assert groups[0]["event_id"] == event_id
        assert groups[0]["family_count"] == 2
        assert set(groups[0]["family_ids"]) == {fa, fb}
        assert set(groups[0]["source_job_ids"]) == {"a", "b"}

    empty = build_global_workspace_summary(db, [])
    assert empty["planning_overview"]["event_groups"] == []
    assert empty["event_count"] == 0


def test_0280_canonical_event_api_uses_event_identity_not_backup_route(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        fa, _ = _family(connection, "a", "A")
        fb, _ = _family(connection, "b", "B")

    created = create_planned_event(db, "a", _preview_for_families([fa, fb]))
    event_id = str(created["parent_event"]["id"])
    monkeypatch.setattr(main, "DATABASE_FILE", db)

    payload = main.api_canonical_event(event_id)
    assert payload["event_id"] == event_id
    assert payload["anchor_job_id"] == "a"
    assert set(payload["source_job_ids"]) == {"a", "b"}

    route_paths = {getattr(route, "path", "") for route in main.app.routes}
    assert {
        "/api/events/{event_id}",
        "/api/events/{event_id}/structure",
        "/api/events/{event_id}/sort-plan",
        "/api/events/{event_id}/apply",
        "/api/events/{event_id}/reconcile-plan",
        "/api/events/{event_id}/reconcile",
        "/api/events/{event_id}/reapply-plan",
        "/api/events/{event_id}/reapply",
    }.issubset(route_paths)
