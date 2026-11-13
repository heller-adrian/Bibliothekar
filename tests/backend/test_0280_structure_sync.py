"""0.28.0: manual Finder structure synchronization for Applied and Archived events."""
from __future__ import annotations
from tests.backend.legacy_storage_fixture import provision_legacy_storage

from pathlib import Path
import json

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.external_changes import (
    list_external_change_state,
    repair_external_conflicts,
)
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
    provision_legacy_storage(workspace)
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
    assert "Assign Later" in prepared_path.parts

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


def test_0280_event_edit_ui_has_one_subfolder_control_per_event_kind():
    source = Path("app/events_ui.py").read_text(encoding="utf-8")
    assert source.count('id="edit-subfolders"') == 1
    assert 'document.getElementById("edit-subfolders").checked' in source
    assert source.count('window.BibliothekarFolderLayout.eventEditor(') == 1


def test_0280_structure_task_auto_opens_once_per_page():
    source = Path("app/ui_shell.py").read_text(encoding="utf-8")
    assert 'let structureTaskAutoOpened = false;' in source
    assert 'task.kind === "event_structure_change"' in source
    assert 'if (taskPanel?.hasAttribute("hidden")) openTaskPanel();' in source


def test_0413_applied_event_root_rename_is_found_by_event_document(tmp_path: Path):
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
    (event_root / "event.json").write_text(
        json.dumps({"event": {"id": "e"}}),
        encoding="utf-8",
    )
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

    renamed = event_root.with_name("Urlaub Neu")
    event_root.rename(renamed)
    observed = scan_event_inventory(
        db,
        work_root,
        "j",
        "e",
        root_kind="shared_workspace",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    assert observed["event_prefix"] == "2026/Urlaub Neu"

    change = detect_event_structure_change(db, "e")
    assert change is not None
    assert change["status"] == "pending"
    assert change["detected"]["root_rename"]["old_folder"] == "07-23 - Trip"
    assert change["detected"]["root_rename"]["new_folder"] == "Urlaub Neu"
    assert change["detected"]["placement_conflicts"] == []

    confirmed = confirm_applied_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Alle",
        app_version="0.41.3",
    )
    assert confirmed["status"] == "completed"
    with database_connection(db) as connection:
        event = connection.execute(
            "SELECT folder_name FROM events WHERE id='e'"
        ).fetchone()
        file_row = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(event["folder_name"]) == "Urlaub Neu"
    assert str(file_row["current_relative_path"]) == "2026/Urlaub Neu/Alle/A.JPG"
    assert (renamed / "event.json").is_file()


def test_0413_applied_child_root_rename_is_one_structure_change(tmp_path: Path):
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
    old_child = "07-23 00-00 - 07-23 23-59 - A"
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,
                   end_datetime,uses_time_range,folder_name,status,created_at,
                   updated_at,event_kind,preserve_day_folders,revision,
                   applied_at,resort_required,time_model_version,timeline_model)
               VALUES ('c','j','e','child','A','2026-07-23T00:00:00',
                       '2026-07-23T23:59:59',1,?,'applied',?,?, 'event',0,1,?,0,2,'continuous')""",
            (old_child, NOW, NOW, NOW),
        )
        connection.execute(
            "UPDATE event_assignments SET event_id='c' WHERE event_id='e'"
        )
        connection.execute(
            """UPDATE files
               SET current_relative_path=?
               WHERE id=?""",
            (f"2026/07-23 - Trip/{old_child}/Alle/A.JPG", file_id),
        )

    event_root = work_root / "2026" / "07-23 - Trip"
    child_root = event_root / old_child
    for name in ("Alle", "Sortiert", "Export"):
        (child_root / name).mkdir(parents=True, exist_ok=True)
    (child_root / "Alle" / "A.JPG").write_bytes(b"camera-a")
    (event_root / "event.json").write_text(
        json.dumps({"event": {"id": "e"}}),
        encoding="utf-8",
    )

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
    child_root.rename(event_root / "A")
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
    assert change["detected"]["placement_conflicts"] == []
    assert change["detected"]["directory_added"] == []
    assert change["detected"]["directory_removed"] == []
    assert change["detected"]["child_renames"] == [{
        "child_event_id": "c",
        "old_folder": old_child,
        "new_folder": "A",
    }]

    confirmed = confirm_applied_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Alle",
        app_version="0.41.3",
    )
    assert confirmed["status"] == "completed"
    with database_connection(db) as connection:
        child = connection.execute(
            "SELECT folder_name FROM events WHERE id='c'"
        ).fetchone()
        file_row = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(child["folder_name"]) == "A"
    assert str(file_row["current_relative_path"]) == "2026/07-23 - Trip/A/Alle/A.JPG"

def test_0414_applied_file_moved_to_wrong_subevent_is_repaired_to_semantic_leaf(
    tmp_path: Path,
):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_workspace_layout(workspace)
    work_root = shared_work_root(workspace)
    central_root = Path(layout["backup_root"])

    _family_id, file_id = _seed_event_with_legacy_layout(
        db,
        status="applied",
        current_root_kind="shared_workspace",
    )
    with database_connection(db) as connection:
        for child_id, name in (("c1", "Tag 1"), ("c2", "Tag 2")):
            connection.execute(
                """INSERT INTO events(
                       id,job_id,parent_event_id,event_level,name,start_datetime,
                       end_datetime,uses_time_range,folder_name,status,created_at,
                       updated_at,event_kind,preserve_day_folders,revision,
                       applied_at,resort_required,time_model_version,timeline_model)
                   VALUES (?, 'j','e','child',?,'2026-07-23T00:00:00',
                           '2026-07-23T23:59:59',1,?,'applied',?,?, 'event',0,1,?,0,2,'continuous')""",
                (child_id, name, name, NOW, NOW, NOW),
            )
        connection.execute(
            "UPDATE event_assignments SET event_id='c1' WHERE event_id='e'"
        )
        connection.execute(
            """UPDATE files
               SET current_relative_path=?
               WHERE id=?""",
            ("2026/07-23 - Trip/Tag 1/Alle/A.JPG", file_id),
        )

    event_root = work_root / "2026" / "07-23 - Trip"
    for child in ("Tag 1", "Tag 2"):
        for name in ("Alle", "Sortiert", "Export"):
            (event_root / child / name).mkdir(parents=True, exist_ok=True)
    expected = event_root / "Tag 1" / "Alle" / "A.JPG"
    observed = event_root / "Tag 2" / "Alle" / "A.JPG"
    expected.write_bytes(b"camera-a")

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
    detect_event_structure_change(db, "e")

    observed.parent.mkdir(parents=True, exist_ok=True)
    expected.rename(observed)
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
    detect_event_structure_change(db, "e")

    # Ein weiterer Reload/Reconcile darf den fachlichen Sollpfad nicht durch
    # den inzwischen in SQLite übernommenen falschen IST-Pfad ersetzen.
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
    detect_event_structure_change(db, "e")

    state = list_external_change_state(db)
    assert state["required_count"] == 1
    notice = state["required"][0]
    assert notice["kind"] == "placement_conflict"
    assert notice["details"]["expected_relative_path"] == (
        "2026/07-23 - Trip/Tag 1/Alle/A.JPG"
    )
    assert notice["details"]["observed_relative_path"] == (
        "2026/07-23 - Trip/Tag 2/Alle/A.JPG"
    )
    with database_connection(db) as connection:
        current = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    # The catalogue retains the semantic SOLL location; the observed wrong
    # physical IST location is retained separately in the durable notice.
    # Repair must still be exercised below (SHA, destination and notice).
    assert str(current["current_relative_path"]) == (
        "2026/07-23 - Trip/Tag 1/Alle/A.JPG"
    )

    repaired = repair_external_conflicts(
        db,
        central_root=central_root,
        library_work_root=work_root,
    )
    assert repaired["repaired_count"] == 1
    assert repaired["skipped"] == []
    assert expected.read_bytes() == b"camera-a"
    assert not observed.exists()
    with database_connection(db) as connection:
        current = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert tuple(current) == (
        "2026/07-23 - Trip/Tag 1/Alle/A.JPG",
        "shared_workspace",
    )
    assert list_external_change_state(db)["required_count"] == 0

