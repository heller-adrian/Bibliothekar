"""0.28.0: manual Finder structure synchronization for Applied and Archived events."""
from __future__ import annotations

from pathlib import Path

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot, get_event_layout, layout_paths
from app.event_structure_changes import (
    confirm_applied_structure_change,
    detect_event_structure_change,
    prepare_archived_structure_change,
    verify_archived_structure_change,
)
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW,
    seed_event,
    seed_family,
    seed_job,
)


def _seed_event_with_legacy_layout(
    db: Path,
    *,
    status: str,
    current_root_kind: str,
) -> tuple[int, int]:
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status=status)
        family_id, file_id = seed_family(
            connection,
            content=b"camera-a",
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        connection.execute(
            "UPDATE files SET current_root_kind=? WHERE id=?",
            (current_root_kind, file_id),
        )
        ensure_event_layout_snapshot(connection, "e", now=NOW)
    return family_id, file_id


def _materialize_legacy_tree(root: Path) -> Path:
    event_root = root / "2026" / "07-23 - Trip"
    for name in ("Alle", "Sortiert", "Export"):
        (event_root / name).mkdir(parents=True, exist_ok=True)
    (event_root / "Alle" / "A.JPG").write_bytes(b"camera-a")
    return event_root


def test_0280_applied_manual_rename_is_detected_and_adopted_once(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work_root = shared_work_root(workspace)

    _family_id, file_id = _seed_event_with_legacy_layout(
        db,
        status="applied",
        current_root_kind="shared_workspace",
    )
    event_root = _materialize_legacy_tree(work_root)

    baseline = scan_event_inventory(
        db,
        work_root,
        "j",
        "e",
        root_kind="shared_workspace",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    assert baseline["summary"]["missing_known_file_ids"] == []
    assert detect_event_structure_change(db, "e") is None

    (event_root / "Alle").rename(event_root / "Originale")
    scan_event_inventory(
        db,
        work_root,
        "j",
        "e",
        root_kind="shared_workspace",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    change = detect_event_structure_change(db, "e")
    assert change is not None
    assert change["status"] == "pending"
    detected = change["detected"]
    assert "Originale" in detected["input_options"]
    assert detected["current_input_path"] == "Alle"
    assert "Alle" in detected["directory_removed"]
    assert "Originale" in detected["directory_added"]
    assert len(detected["file_moves"]) == 1

    confirmed = confirm_applied_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Originale",
        app_version="0.28.0",
    )
    assert confirmed["status"] == "completed"

    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        layout = get_event_layout(connection, "e")
    assert tuple(row) == (
        "2026/07-23 - Trip/Originale/A.JPG",
        "shared_workspace",
    )
    assert layout["input_path"] == "Originale"
    assert set(layout_paths(layout["layout"])) == {"Originale", "Sortiert", "Export"}

    event_json = event_root / "event.json"
    assert event_json.is_file()

    # Same unchanged Finder state is now canonical and must not create another task.
    scan_event_inventory(
        db,
        work_root,
        "j",
        "e",
        root_kind="shared_workspace",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    assert detect_event_structure_change(db, "e") is None


def test_0280_archived_manual_rename_requires_staged_event_json_before_commit(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    ensure_workspace_layout(workspace)

    _family_id, file_id = _seed_event_with_legacy_layout(
        db,
        status="archived",
        current_root_kind="camera_archive",
    )
    event_root = _materialize_legacy_tree(archive)

    scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    assert detect_event_structure_change(db, "e") is None

    (event_root / "Alle").rename(event_root / "Originale")
    scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    change = detect_event_structure_change(db, "e")
    assert change is not None
    assert change["status"] == "pending"
    assert "Originale" in change["detected"]["input_options"]

    prepared = prepare_archived_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Originale",
        app_version="0.28.0",
    )
    prepared_path = Path(prepared["prepared_event_json_path"])
    assert prepared["status"] == "prepared"
    assert prepared_path.is_file()
    assert "Später zuordnen" in prepared_path.parts

    # Bibliothekar itself does not write the archive. Emulate the user's manual
    # replacement, then let Bibliothekar verify the exact prepared document.
    archive_document = event_root / "event.json"
    archive_document.write_bytes(prepared_path.read_bytes())

    verified = verify_archived_structure_change(
        db,
        archive,
        workspace,
        change["id"],
    )
    assert verified["status"] == "completed"
    assert verified["archive_read_only"] is True

    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        layout = get_event_layout(connection, "e")
    assert tuple(row) == (
        "2026/07-23 - Trip/Originale/A.JPG",
        "camera_archive",
    )
    assert layout["input_path"] == "Originale"
    assert set(layout_paths(layout["layout"])) == {"Originale", "Sortiert", "Export"}

    assert detect_event_structure_change(db, "e") is None
