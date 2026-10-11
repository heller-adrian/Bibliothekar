from __future__ import annotations

from app.archive_staging import staging_directory_name
from app.workspace_layout import shared_work_root

from pathlib import Path

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot, get_event_layout, layout_paths, update_event_layout
from app.event_change_request import propose_event_change
from app.event_change_apply import confirm_event_change, verify_event_change, finish_event_change
from app.archive_change_document import build_projected_archive_event_document
from app.archive_staging import required_event_document_for_request
from app.event_mutation import capture_job_event_state, begin_mutation, cancel_mutation
from app.event_structure_changes import (
    confirm_applied_structure_change,
    detect_event_structure_change,
    prepare_archived_structure_change,
    verify_archived_structure_change,
)
from app.sort_apply import CONFIRMATION_PHRASE
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    prepare_workspace_reconcile_run,
    execute_workspace_reconcile_run,
)
from tests.backend.test_0263_event_inventory import (
    NOW,
    seed_event,
    seed_family,
    seed_job,
)


def _seed_applied_workspace(db: Path, workspace: Path) -> tuple[Path, int]:
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work_root = shared_work_root(workspace)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="applied")
        family_id, file_id = seed_family(
            connection,
            content=b"camera-a",
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        connection.execute(
            "UPDATE files SET current_root_kind='shared_workspace' WHERE id=?",
            (file_id,),
        )
        ensure_event_layout_snapshot(connection, "e", now=NOW)

    event_root = work_root / "2026" / "07-23 - Trip"
    for name in ("Alle", "Sortiert", "Export"):
        (event_root / name).mkdir(parents=True, exist_ok=True)
    (event_root / "Alle" / "A.JPG").write_bytes(b"camera-a")
    (event_root / "Alle" / "A.xmp").write_bytes(b"xmp-a")
    (event_root / "Export" / "A.jpg").write_bytes(b"export-a")

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
    return event_root, file_id


def _reconcile(db: Path, workspace: Path) -> dict:
    plan = build_workspace_reconcile_plan(db, "j", "e", workspace)
    assert plan["summary"]["ready"] is True
    run = prepare_workspace_reconcile_run(
        db,
        "j",
        "e",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)
    return plan


def test_0283_structure_off_flattens_camera_xmp_and_export_without_manual_task(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    event_root, file_id = _seed_applied_workspace(db, workspace)

    # Finder/SMB-Metadaten dürfen einen von Bibliothekar selbst obsolet
    # gemachten verwalteten Ordner nicht künstlich am Leben halten.
    (event_root / "Alle" / ".DS_Store").write_bytes(b"finder")
    (event_root / "Alle" / "._A.JPG").write_bytes(b"appledouble")

    with database_connection(db) as connection:
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )
        connection.execute("UPDATE events SET resort_required=1 WHERE id='e'")

    plan = _reconcile(db, workspace)
    assert plan["summary"]["camera_file_count"] == 1
    assert plan["summary"]["asset_count"] == 2

    assert (event_root / "A.JPG").read_bytes() == b"camera-a"
    assert (event_root / "A.xmp").read_bytes() == b"xmp-a"
    assert (event_root / "A_Export.jpg").read_bytes() == b"export-a"
    assert not (event_root / "Alle").exists()
    assert not (event_root / "Sortiert").exists()
    assert not (event_root / "Export").exists()

    work_root = shared_work_root(workspace)
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

    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        layout = get_event_layout(connection, "e")
    assert row["current_relative_path"] == "2026/07-23 - Trip/A.JPG"
    assert layout["structure_enabled"] is False


def test_0283_structure_reenabled_puts_everything_in_current_input_without_snapshot(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    event_root, _file_id = _seed_applied_workspace(db, workspace)

    # First flatten the event completely.
    with database_connection(db) as connection:
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )
        connection.execute("UPDATE events SET resort_required=1 WHERE id='e'")
    _reconcile(db, workspace)

    # Re-enable the standard structure. No historic placement is restored:
    # every existing file goes into the selected input folder.
    with database_connection(db) as connection:
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=True,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )
        connection.execute("UPDATE events SET resort_required=1 WHERE id='e'")

    work_root = shared_work_root(workspace)
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
    _reconcile(db, workspace)

    assert (event_root / "Alle" / "A.JPG").read_bytes() == b"camera-a"
    assert (event_root / "Alle" / "A.xmp").read_bytes() == b"xmp-a"
    assert (event_root / "Alle" / "A_Export.jpg").read_bytes() == b"export-a"
    assert (event_root / "Sortiert").is_dir()
    assert (event_root / "Export").is_dir()
    assert not (event_root / "A.JPG").exists()
    assert not (event_root / "A.xmp").exists()
    assert not (event_root / "A_Export.jpg").exists()

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


def test_0283_manual_folder_created_while_structure_off_reenables_applied_layout(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    event_root, _file_id = _seed_applied_workspace(db, workspace)

    with database_connection(db) as connection:
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )
        connection.execute("UPDATE events SET resort_required=1 WHERE id='e'")
    _reconcile(db, workspace)

    manual = event_root / "Auswahl"
    manual.mkdir()
    (event_root / "A.JPG").replace(manual / "A.JPG")

    work_root = shared_work_root(workspace)
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
    assert change["detected"]["proposed_structure_enabled"] is True
    assert "Auswahl" in change["detected"]["input_options"]

    done = confirm_applied_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Auswahl",
        app_version="0.28.3",
    )
    assert done["status"] == "completed"

    with database_connection(db) as connection:
        layout = get_event_layout(connection, "e")
    assert layout["structure_enabled"] is True
    assert layout["input_path"] == "Auswahl"
    assert set(layout_paths(layout["layout"])) == {"Auswahl"}


def test_0283_manual_folder_created_while_structure_off_reenables_archived_layout(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    ensure_workspace_layout(workspace)

    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        _family_id, file_id = seed_family(
            connection,
            content=b"camera-a",
            current_path="2026/07-23 - Trip/A.JPG",
        )
        connection.execute(
            "UPDATE files SET current_root_kind='camera_archive' WHERE id=?",
            (file_id,),
        )
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )

    event_root = archive / "2026" / "07-23 - Trip"
    event_root.mkdir(parents=True)
    (event_root / "A.JPG").write_bytes(b"camera-a")

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

    manual = event_root / "Auswahl"
    manual.mkdir()
    (event_root / "A.JPG").replace(manual / "A.JPG")

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
    assert change["detected"]["proposed_structure_enabled"] is True

    prepared = prepare_archived_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Auswahl",
        app_version="0.28.3",
    )
    prepared_path = Path(prepared["prepared_event_json_path"])
    (event_root / "event.json").write_bytes(prepared_path.read_bytes())

    verified = verify_archived_structure_change(
        db,
        archive,
        workspace,
        change["id"],
    )
    assert verified["status"] == "completed"
    assert verified["helper_cleanup"]["removed_file_count"] == 1
    assert not prepared_path.exists()
    assert not prepared_path.parent.exists()
    assert not prepared_path.parent.parent.exists()
    with database_connection(db) as connection:
        layout = get_event_layout(connection, "e")
    assert layout["structure_enabled"] is True
    assert layout["input_path"] == "Auswahl"
    assert set(layout_paths(layout["layout"])) == {"Auswahl"}


def test_0283_legacy_manual_archive_helper_does_not_block_next_archive_change(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    ensure_workspace_layout(workspace)

    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, file_id = seed_family(
            connection,
            content=b"camera-a",
            current_path="2026/07-23 - Trip/A.JPG",
        )
        connection.execute(
            "UPDATE files SET current_root_kind='camera_archive' WHERE id=?",
            (file_id,),
        )
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )

    event_root = archive / "2026" / "07-23 - Trip"
    event_root.mkdir(parents=True)
    (event_root / "A.JPG").write_bytes(b"camera-a")

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
    manual = event_root / "Auswahl"
    manual.mkdir()
    (event_root / "A.JPG").replace(manual / "A.JPG")
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

    prepared = prepare_archived_structure_change(
        db,
        workspace,
        change["id"],
        input_path="Auswahl",
        app_version="0.28.3",
    )
    prepared_path = Path(prepared["prepared_event_json_path"])
    legacy_payload = prepared_path.read_bytes()
    (event_root / "event.json").write_bytes(legacy_payload)
    verify_archived_structure_change(db, archive, workspace, change["id"])
    assert not prepared_path.exists()

    # Simuliere genau den Altbestand eines früheren 0.28.3-Builds, der die
    # bereits abgeschlossene Hilfs-event.json nicht entfernt hatte.
    prepared_path.parent.mkdir(parents=True, exist_ok=True)
    prepared_path.write_bytes(legacy_payload)

    with database_connection(db) as connection:
        state = get_event_layout(connection, "e")
    proposed = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, False),
        event_name="Trip",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirmed = confirm_event_change(db, cr_id, archive, workspace)
    assert confirmed["status"] == "bestaetigt"

    spec = required_event_document_for_request(db, cr_id)
    assert spec is not None
    staged = shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace)) / spec["target_relative_path"]
    assert staged.is_file()
    assert staged.read_bytes() != legacy_payload


def _seed_archived_layout_event(
    db: Path,
    workspace: Path,
    archive: Path,
    *,
    structure_enabled: bool,
) -> tuple[Path, int, dict]:
    initialize_database(db)
    ensure_workspace_layout(workspace)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, file_id = seed_family(
            connection,
            content=b"camera-a",
            current_path=(
                "2026/07-23 - Trip/Alle/A.JPG"
                if structure_enabled
                else "2026/07-23 - Trip/A.JPG"
            ),
        )
        connection.execute(
            "UPDATE files SET current_root_kind='camera_archive' WHERE id=?",
            (file_id,),
        )
        state = ensure_event_layout_snapshot(connection, "e", now=NOW)
        if not structure_enabled:
            update_event_layout(
                connection,
                "e",
                structure_enabled=False,
                input_path=state["input_path"],
                layout=state["layout"],
                updated_at=NOW,
            )
            state = get_event_layout(connection, "e")

    event_root = archive / "2026" / "07-23 - Trip"
    if structure_enabled:
        (event_root / "Alle").mkdir(parents=True)
        (event_root / "Sortiert").mkdir()
        (event_root / "Export").mkdir()
        (event_root / "Alle" / "A.JPG").write_bytes(b"camera-a")
        (event_root / "Alle" / "A.xmp").write_bytes(b"xmp-a")
        (event_root / "Export" / "A.jpg").write_bytes(b"export-a")
    else:
        event_root.mkdir(parents=True)
        (event_root / "A.JPG").write_bytes(b"camera-a")
        (event_root / "A.xmp").write_bytes(b"xmp-a")

    return event_root, family_id, state


def _archived_layout_preview(family_id: int, state: dict, enabled: bool) -> dict:
    return {
        "event_kind": "event",
        "event_name": "Trip",
        "parent_folder": "07-23 - Trip",
        "child_folder": None,
        "uses_time_range": False,
        "preserve_day_folders": False,
        "start_date": "2026-07-23",
        "end_date": "2026-07-23",
        "start_time": None,
        "end_time": None,
        "selected_day_keys": ["2026-07-23"],
        "selected_family_ids": [family_id],
        "selected_file_count": 1,
        "selected_family_count": 1,
        "subevents": [],
        "folder_layout": {
            "structure_enabled": enabled,
            "input_path": str(state["input_path"]),
            "layout": state["layout"],
        },
        "create_subfolders": enabled,
        "_folder_layout_explicit": True,
    }


def test_0283_direct_archived_structure_off_flattens_camera_and_sidecar_plan(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    _event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    result = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, False),
        event_name="Trip",
        archive_root=archive,
        workspace_path=workspace,
    )
    plan = result["plan"]
    camera_targets = {
        str(item["new_path"]) for item in plan["families_with_plans"]
    }
    xmp_targets = {
        str(item["new_path"])
        for item in plan["assets_with_plans"]
        if str(item.get("asset_kind")) == "xmp"
    }
    export_targets = {
        str(item["new_path"])
        for item in plan["assets_with_plans"]
        if str(item.get("asset_kind")) == "export"
    }
    assert camera_targets == {"2026/07-23 - Trip/A.JPG"}
    assert xmp_targets == {"2026/07-23 - Trip/A.xmp"}
    assert export_targets == {"2026/07-23 - Trip/A_Export.jpg"}

    with database_connection(db) as connection:
        cr = dict(connection.execute(
            "SELECT * FROM event_change_requests WHERE id=?",
            (result["change_request_id"],),
        ).fetchone())
    assert cr["folder_structure_enabled"] == 0
    assert cr["folder_input_path"] == "Alle"
    assert cr["folder_layout_json"]

    document = build_projected_archive_event_document(
        db, result["change_request_id"]
    )
    assert document is not None
    assert document["folder_layout"]["structure_enabled"] is False
    assert document["folder_layout"]["input_path"] == "Alle"


def test_0283_direct_archived_structure_reenabled_routes_everything_to_input(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    _event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=False
    )

    result = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, True),
        event_name="Trip",
        archive_root=archive,
        workspace_path=workspace,
    )
    plan = result["plan"]
    camera_targets = {
        str(item["new_path"]) for item in plan["families_with_plans"]
    }
    xmp_targets = {
        str(item["new_path"])
        for item in plan["assets_with_plans"]
        if str(item.get("asset_kind")) == "xmp"
    }
    assert camera_targets == {"2026/07-23 - Trip/Alle/A.JPG"}
    assert xmp_targets == {"2026/07-23 - Trip/Alle/A.xmp"}

    document = build_projected_archive_event_document(
        db, result["change_request_id"]
    )
    assert document is not None
    assert document["folder_layout"]["structure_enabled"] is True
    assert document["folder_layout"]["input_path"] == "Alle"
    assert set(layout_paths(document["folder_layout"]["layout"])) == {
        "Alle", "Sortiert", "Export"
    }


def test_0283_cancel_applied_layout_change_restores_layout_and_creates_no_manual_task(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _event_root, _file_id = _seed_applied_workspace(db, workspace)

    with database_connection(db) as connection:
        original = capture_job_event_state(connection, "j")
        mutation_id = begin_mutation(
            connection,
            job_id="j",
            anchor_event_id="e",
            mutation_kind="edit",
            affected_event_ids=["e"],
            original_state=original,
            status="pending_apply",
        )
        current = get_event_layout(connection, "e")
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path=current["input_path"],
            layout=current["layout"],
            updated_at=NOW,
        )
        connection.execute(
            "UPDATE events SET resort_required=1 WHERE id='e'"
        )
        cancel_mutation(
            connection,
            mutation_id,
            "j",
            workspace_path=workspace,
        )
        connection.commit()

    with database_connection(db) as connection:
        restored = get_event_layout(connection, "e")
        event = connection.execute(
            "SELECT resort_required FROM events WHERE id='e'"
        ).fetchone()
    assert restored["structure_enabled"] is True
    assert restored["input_path"] == "Alle"
    assert int(event["resort_required"] or 0) == 0

    work_root = shared_work_root(workspace)
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


def test_0283_archived_structure_off_finishes_without_followup_manual_task(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    proposed = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, False),
        event_name="Trip",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)

    # Emuliere genau den von der App geführten manuellen Archivschritt.
    (event_root / "Alle" / "A.JPG").replace(event_root / "A.JPG")
    (event_root / "Alle" / "A.xmp").replace(event_root / "A.xmp")
    (event_root / "Export" / "A.jpg").replace(event_root / "A_Export.jpg")
    (event_root / "Alle").rmdir()
    (event_root / "Sortiert").rmdir()
    (event_root / "Export").rmdir()

    spec = required_event_document_for_request(db, cr_id)
    assert spec is not None
    staged_document = shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace)) / spec["target_relative_path"]
    assert staged_document.is_file()
    (archive / spec["target_relative_path"]).write_bytes(staged_document.read_bytes())

    verified = verify_event_change(db, cr_id, archive, workspace)
    assert verified["complete"] is True
    finished = finish_event_change(db, cr_id, archive, workspace)
    assert finished["status"] == "archiviert"

    # Nach dem vollständig app-geführten Auftrag ist der neue Zustand kanonisch;
    # derselbe Umbau darf nicht noch einmal als manuelle Ereignisänderung auftauchen.
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

    with database_connection(db) as connection:
        layout = get_event_layout(connection, "e")
    assert layout["structure_enabled"] is False
