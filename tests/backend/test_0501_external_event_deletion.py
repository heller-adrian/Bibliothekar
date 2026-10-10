"""0.50.1: external event-directory deletion vs. manual moves.

Every file and SQLite database here is synthetic and inside pytest's tmp_path.
The production archive, workspace and database are never used.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    initialize_database,
    list_global_tasks,
)
from app.event_inventory import scan_event_inventory
from app.event_structure_changes import detect_all_event_structure_changes
from app.external_changes import acknowledge_external_notices, list_external_change_state
from app.live_inventory import refresh_live_event_inventories
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-10T17:00:00+00:00"


def _case(tmp_path: Path):
    db = tmp_path / "database.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    create_job(
        db, job_id="J", kind="sd_import", trigger_type="approved_sd",
        source_path="/synthetic/source", working_path="/synthetic/workspace",
        operation="folder_import",
    )
    return db, workspace, archive, Path(layout["work_root"])


def _event(
    db: Path, physical_root: Path, *,
    name: str, day: str, items: list[tuple[str, bytes, str]],
    status: str = "applied",
):
    families = []
    file_ids = []
    with database_connection(db) as connection:
        for filename, data, _branch in items:
            digest = hashlib.sha256(data).hexdigest()
            cursor = connection.execute(
                """INSERT INTO file_families(
                       job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence)
                   VALUES ('J',?,?, 'complete',?, 'high')""",
                (name + filename, Path(filename).stem, day + "T12:00:00"),
            )
            family_id = int(cursor.lastrowid)
            cursor = connection.execute(
                """INSERT INTO files(
                       job_id,family_id,original_relative_path,
                       current_relative_path,original_filename,extension,
                       media_type,size_bytes,sha256_original,sha256_current,
                       selected_capture_time,selected_capture_source,
                       capture_time_confidence,review_status,metadata_write_status,
                       current_root_kind,created_at,updated_at)
                   VALUES ('J',?,?,?,?,'.JPG','jpeg',?,?,?,?,'qa',
                           'high','not_required','not_requested',
                           'shared_workspace',?,?)""",
                (
                    family_id, day + "/" + filename, day + "/" + filename,
                    filename, len(data), digest, digest, day + "T12:00:00",
                    NOW, NOW,
                ),
            )
            families.append(family_id)
            file_ids.append(int(cursor.lastrowid))

    result = create_planned_event(db, "J", {
        "event_kind": "event", "event_name": name,
        "start_date": day, "end_date": day,
        "start_time": "00:00", "end_time": "23:59",
        "uses_time_range": False, "preserve_day_folders": False,
        "parent_folder": day[5:7] + "." + day[8:10] + " - " + name,
        "child_folder": None, "child_event_name": None,
        "selected_family_ids": families, "structure_lines": [],
    })
    event_id = str(result["parent_event"]["id"])
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE events SET status=?,applied_at=?,archived_at=? WHERE id=?",
            (status, NOW, NOW if status == "archived" else None, event_id),
        )
        folder = str(connection.execute(
            "SELECT folder_name FROM events WHERE id=?", (event_id,)
        ).fetchone()[0])
        root = physical_root / day[:4] / folder
        for filename, data, branch in items:
            target = root / branch / filename if branch else root / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for branch in ("Alle", "Sortiert", "Export"):
            (root / branch).mkdir(parents=True, exist_ok=True)
        for fid, (filename, _, branch) in zip(file_ids, items):
            relative = (Path(day[:4]) / folder / branch / filename).as_posix()
            connection.execute(
                """UPDATE files SET current_root_kind=?,current_relative_path=?
                   WHERE id=?""",
                ("camera_archive" if status == "archived" else "shared_workspace",
                 relative, fid),
            )
    scan_event_inventory(
        db, physical_root, "J", event_id,
        root_kind="camera_archive" if status == "archived" else "shared_workspace",
    )
    return event_id, root, file_ids


@pytest.mark.parametrize("status", ["applied", "archived"])
def test_removed_whole_event_root_is_acknowledgeable_and_survives_restart(
    tmp_path: Path, status: str,
):
    db, workspace, archive, work = _case(tmp_path)
    physical_root = archive if status == "archived" else work
    event_id, root, file_ids = _event(
        db, physical_root, name="Deleted", day="2026-10-05",
        items=[("A.JPG", b"original-a", "Alle"), ("B.JPG", b"original-b", "Alle")],
        status=status,
    )
    shutil.rmtree(root)
    first = refresh_live_event_inventories(db, workspace, archive)
    assert first["errors"] == []
    assert first["events"][event_id]["event_root_missing"]
    detect_all_event_structure_changes(db)
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM files WHERE id IN (?,?)", file_ids
        ).fetchone()[0] == 2

    # The second full observation accepts the user deletion, never restores it.
    second = refresh_live_event_inventories(db, workspace, archive)
    assert second["errors"] == []
    detect_all_event_structure_changes(db)
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM files WHERE id IN (?,?)", file_ids
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id=?", (event_id,)
        ).fetchone()[0] == 0
    state = list_external_change_state(db)
    assert state["required_count"] == 0
    assert len([n for n in state["informational"] if n["kind"] == "event_root_deleted"]) == 1
    assert not root.exists()

    notice = next(n for n in state["informational"] if n["kind"] == "event_root_deleted")
    acknowledge_external_notices(db, [notice["id"]])
    assert list_external_change_state(db)["informational_count"] == 0
    refresh_live_event_inventories(db, workspace, archive)
    detect_all_event_structure_changes(db)
    assert list_external_change_state(db)["informational_count"] == 0
    assert not root.exists()


def test_partial_directory_removal_does_not_delete_other_files(tmp_path: Path):
    db, workspace, archive, work = _case(tmp_path)
    event_id, root, ids = _event(
        db, work, name="Partial", day="2026-10-05",
        items=[("A.JPG", b"kept", "Alle"), ("B.JPG", b"deleted", "Sortiert")],
    )
    shutil.rmtree(root / "Sortiert")
    for _ in range(2):
        refreshed = refresh_live_event_inventories(db, workspace, archive)
        assert refreshed["errors"] == []
        detect_all_event_structure_changes(db)
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (ids[0],)).fetchone()
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (ids[1],)).fetchone() is None
        assert connection.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone()
    assert (root / "Alle" / "A.JPG").read_bytes() == b"kept"
    assert not (root / "Sortiert").exists()
    state = list_external_change_state(db)
    assert state["required_count"] == 0
    notice = next(
        item for item in state["informational"]
        if item["kind"] == "event_directory_deleted"
    )
    assert notice["details"]["deleted_file_count"] == 1
    assert notice["details"]["directories"] == ["Sortiert"]
    acknowledge_external_notices(db, [notice["id"]])
    assert list_external_change_state(db)["informational_count"] == 0
    refresh_live_event_inventories(db, workspace, archive)
    detect_all_event_structure_changes(db)
    assert list_external_change_state(db)["informational_count"] == 0
    assert all(
        task["kind"] != "event_structure_change"
        for task in list_global_tasks(db)
    )


def test_wrong_event_move_is_conflict_not_deleted(tmp_path: Path):
    db, workspace, archive, work = _case(tmp_path)
    event_a, root_a, ids_a = _event(
        db, work, name="Source", day="2026-10-05",
        items=[("A.JPG", b"moved-original", "Alle")],
    )
    _event_b, root_b, _ids_b = _event(
        db, work, name="Destination", day="2026-10-06",
        items=[("B.JPG", b"unrelated", "Alle")],
    )
    (root_a / "Alle" / "A.JPG").replace(root_b / "Alle" / "A.JPG")
    for _ in range(3):
        refresh_live_event_inventories(db, workspace, archive)
        detect_all_event_structure_changes(db)
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (ids_a[0],)).fetchone()
        assert connection.execute("SELECT 1 FROM events WHERE id=?", (event_a,)).fetchone()
    state = list_external_change_state(db)
    assert state["required_count"] >= 1
    assert (root_b / "Alle" / "A.JPG").is_file()


def test_unavailable_root_is_not_interpreted_as_a_deletion(tmp_path: Path):
    db, workspace, archive, work = _case(tmp_path)
    event_id, _root, file_ids = _event(
        db, work, name="Unavailable", day="2026-10-05",
        items=[("A.JPG", b"still-known", "Alle")],
    )
    shutil.rmtree(work)
    for _ in range(3):
        result = refresh_live_event_inventories(db, workspace, archive)
        assert result["errors"]
        detect_all_event_structure_changes(db)
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone()
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (file_ids[0],)).fetchone()


@pytest.mark.parametrize("status", ["applied", "archived"])
def test_0501_manual_root_rename_is_not_deletion(tmp_path: Path, status: str):
    import json
    db, workspace, archive, work = _case(tmp_path)
    root_base = archive if status == "archived" else work
    event_id, root, file_ids = _event(
        db, root_base, name="Renamed", day="2026-10-05",
        items=[("A.JPG", b"renamed-not-deleted", "Alle")],
        status=status,
    )
    (root / "event.json").write_text(
        json.dumps({"event": {"id": event_id}}), encoding="utf-8",
    )
    renamed = root.with_name(root.name + " - renamed")
    root.rename(renamed)
    for _ in range(3):
        summary = refresh_live_event_inventories(db, workspace, archive)
        assert summary["errors"] == []
        assert summary["events"][event_id]["known_file_count"] == 1
        detect_all_event_structure_changes(db)
    with database_connection(db) as c:
        assert c.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone()
        assert c.execute("SELECT 1 FROM files WHERE id=?", (file_ids[0],)).fetchone()
    assert (renamed / "Alle" / "A.JPG").read_bytes() == b"renamed-not-deleted"
    assert all(
        n["kind"] != "event_root_deleted"
        for n in list_external_change_state(db)["informational"]
    )


def test_0501_foreign_assignment_survives_missing_event_root(tmp_path: Path):
    db, workspace, archive, work = _case(tmp_path)
    a, root_a, a_files = _event(
        db, work, name="A", day="2026-10-05",
        items=[("A.JPG", b"owned-a", "Alle")],
    )
    b, root_b, _ = _event(
        db, work, name="B", day="2026-10-06",
        items=[("B.JPG", b"owned-b", "Alle")],
    )
    with database_connection(db) as c:
        family_id = c.execute(
            "SELECT family_id FROM files WHERE id=?", (a_files[0],)
        ).fetchone()[0]
        c.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,assignment_source,created_at)
               VALUES (?,?,'manual',?)""",
            (b, family_id, NOW),
        )
    shutil.rmtree(root_a)
    for _ in range(3):
        refresh_live_event_inventories(db, workspace, archive)
        detect_all_event_structure_changes(db)
    with database_connection(db) as c:
        assert c.execute("SELECT 1 FROM files WHERE id=?", (a_files[0],)).fetchone()
        assert c.execute("SELECT 1 FROM events WHERE id=?", (a,)).fetchone()
        assert c.execute(
            "SELECT 1 FROM event_assignments WHERE event_id=? AND family_id=?",
            (b, family_id),
        ).fetchone()
    assert (root_b / "Alle" / "B.JPG").read_bytes() == b"owned-b"
    assert list_external_change_state(db)["required_count"] >= 1
