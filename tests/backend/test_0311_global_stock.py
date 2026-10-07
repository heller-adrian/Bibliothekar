from __future__ import annotations

from pathlib import Path
import hashlib

from app import main, ui_shell
from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    initialize_database,
)
from app.global_stock import (
    migrate_main_free_stock_to_central,
    project_import_job,
    synchronize_central_stock_projections,
)
from app.safe_transfer import move_verified_no_overwrite
from app.workspace_layout import ensure_workspace_layout
from app.library_registry import (
    MAIN_LIBRARY_ID,
    adopt_main_library,
    claim_source_family,
    get_source_family_claim,
    initialize_library_registry,
    register_library,
)
from app.global_library_inventory import (
    backfill_library_claims,
    backfill_library_inventory,
    occurrence_key,
)


NOW = "2026-10-01T20:00:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _insert_family_file(
    database: Path,
    *,
    job_id: str,
    family_key: str,
    relative_path: str,
    capture_time: str,
    data: bytes,
) -> int:
    digest = _sha(data)
    with database_connection(database) as connection:
        cursor = connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?, ?, ?, 'complete', ?, 'high')""",
            (job_id, family_key, family_key, capture_time),
        )
        family_id = int(cursor.lastrowid)
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at
               )
               VALUES (?, ?, ?, ?, ?, '.JPG', 'jpeg', ?, ?, ?, ?,
                       'qa', 'high', 'not_required', 'not_requested',
                       'shared_workspace', ?, ?)""",
            (
                job_id,
                family_id,
                relative_path,
                relative_path,
                Path(relative_path).name,
                len(data),
                digest,
                digest,
                capture_time,
                NOW,
                NOW,
            ),
        )
    return family_id


def _preview(family_id: int, day: str, name: str) -> dict:
    return {
        "event_kind": "event",
        "event_name": name,
        "start_date": day,
        "end_date": day,
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "parent_folder": f"{day[5:7]}.{day[8:10]} - {name}",
        "child_folder": None,
        "child_event_name": None,
        "selected_family_ids": [family_id],
        "structure_lines": [],
    }


def test_0311_safe_transfer_cross_filesystem_copy_verify_delete(tmp_path, monkeypatch):
    source = tmp_path / "source" / "photo.JPG"
    destination = tmp_path / "other" / "photo.JPG"
    source.parent.mkdir()
    data = b"bibliothekar-cross-filesystem" * 256
    source.write_bytes(data)

    monkeypatch.setattr("app.safe_transfer._same_filesystem", lambda *_: False)

    result = move_verified_no_overwrite(
        source,
        destination,
        expected_size=len(data),
        expected_sha256=_sha(data),
    )

    assert result["method"] == "copy_verify_delete"
    assert not source.exists()
    assert destination.read_bytes() == data
    assert _sha(destination.read_bytes()) == _sha(data)


def test_0311_main_migration_moves_only_free_stock_to_central(tmp_path):
    database = tmp_path / "database" / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_workspace_layout(workspace)
    initialize_database(database)

    create_job(
        database,
        job_id="GLOBAL_IMPORT",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path=layout["work_root"],
        operation="folder_import",
    )

    free_data = b"free-photo"
    applied_data = b"applied-photo"
    free_rel = "2026/2026-10-01/free.JPG"
    applied_rel = "2026/2026-10-02/applied.JPG"
    free_id = _insert_family_file(
        database,
        job_id="GLOBAL_IMPORT",
        family_key="free",
        relative_path=free_rel,
        capture_time="2026-10-01T10:00:00",
        data=free_data,
    )
    applied_id = _insert_family_file(
        database,
        job_id="GLOBAL_IMPORT",
        family_key="applied",
        relative_path=applied_rel,
        capture_time="2026-10-02T10:00:00",
        data=applied_data,
    )

    event = create_planned_event(
        database,
        "GLOBAL_IMPORT",
        _preview(applied_id, "2026-10-02", "Angewendet"),
    )
    event_id = str(event["parent_event"]["id"])
    with database_connection(database) as connection:
        connection.execute(
            "UPDATE events SET status='applied',applied_at=?,updated_at=? WHERE id=?",
            (NOW, NOW, event_id),
        )

    work = Path(layout["work_root"])
    (work / free_rel).parent.mkdir(parents=True, exist_ok=True)
    (work / free_rel).write_bytes(free_data)
    (work / applied_rel).parent.mkdir(parents=True, exist_ok=True)
    (work / applied_rel).write_bytes(applied_data)

    result = migrate_main_free_stock_to_central(database, workspace)
    central = workspace / "SD-Kartensicherungen"

    assert result["migrated"] == 1
    assert (central / free_rel).read_bytes() == free_data
    assert not (work / free_rel).exists()
    assert (work / applied_rel).read_bytes() == applied_data
    assert not (central / applied_rel).exists()

    again = migrate_main_free_stock_to_central(database, workspace)
    assert again["migrated"] == 0
    assert (central / free_rel).read_bytes() == free_data
    assert (work / applied_rel).read_bytes() == applied_data


def test_0311_projection_is_idempotent_and_keeps_local_family_ids(tmp_path):
    source = tmp_path / "main.sqlite3"
    target = tmp_path / "business.sqlite3"
    initialize_database(source)
    initialize_database(target)

    create_job(
        source,
        job_id="GLOBAL_IMPORT",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path="/workspace/SD-Kartensicherungen",
        operation="folder_import",
    )
    data = b"projected-photo"
    _insert_family_file(
        source,
        job_id="GLOBAL_IMPORT",
        family_key="family-a",
        relative_path="2026/2026-10-01/a.JPG",
        capture_time="2026-10-01T12:00:00",
        data=data,
    )

    first = project_import_job(source, target, "GLOBAL_IMPORT")
    second = project_import_job(source, target, "GLOBAL_IMPORT")

    assert first == {"jobs": 1, "families": 1, "files": 1}
    assert second == {"jobs": 0, "families": 0, "files": 0}
    with database_connection(target) as connection:
        family = connection.execute(
            "SELECT id,family_key FROM file_families WHERE job_id='GLOBAL_IMPORT'"
        ).fetchone()
        file_row = connection.execute(
            "SELECT family_id,current_relative_path FROM files WHERE job_id='GLOBAL_IMPORT'"
        ).fetchone()
    assert family is not None and file_row is not None
    assert int(file_row["family_id"]) == int(family["id"])
    assert str(file_row["current_relative_path"]) == "2026/2026-10-01/a.JPG"


def test_0311_settings_contract_has_four_tabs_scroll_and_rounding():
    shell = ui_shell._shell_markup("workspace", "captures")
    assert 'data-bk-settings-area="appearance"' in shell
    assert 'data-bk-settings-area="general"' in shell
    assert 'data-bk-settings-area="folders"' in shell
    assert 'data-bk-settings-area="libraries"' in shell
    assert 'data-bk-settings-area="configuration"' not in shell

    css = ui_shell.BIBLIOTHEKAR_0311_CSS
    assert "overflow-y: auto" in css
    assert "scrollbar-gutter: stable" in css
    assert "#bk-settings-dialog input" in css
    assert "border-radius: 11px" in css
    assert main.DEPLOYMENT_VERSION == "0.41.4"



def test_0311_released_family_refreshes_stale_projection_from_central_stock(tmp_path):
    main_db = tmp_path / "database" / "kamera.sqlite3"
    other_db = tmp_path / "database" / "business.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_workspace_layout(workspace)
    initialize_database(main_db)
    initialize_database(other_db)

    create_job(
        main_db,
        job_id="GLOBAL_RELEASE",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path=str(workspace / "SD-Kartensicherungen"),
        operation="folder_import",
    )
    data = b"released-to-central"
    family_id = _insert_family_file(
        main_db,
        job_id="GLOBAL_RELEASE",
        family_key="release-me",
        relative_path="2026/10.01 - Main/Alle/A.JPG",
        capture_time="2026-10-01T12:00:00",
        data=data,
    )
    project_import_job(main_db, other_db, "GLOBAL_RELEASE")

    with database_connection(other_db) as connection:
        before = connection.execute(
            "SELECT current_relative_path FROM files WHERE job_id='GLOBAL_RELEASE'"
        ).fetchone()
    assert str(before["current_relative_path"]) == "2026/10.01 - Main/Alle/A.JPG"

    central_relative = "2026/2026-10-01/A.JPG"
    central_file = workspace / "SD-Kartensicherungen" / central_relative
    central_file.parent.mkdir(parents=True, exist_ok=True)
    central_file.write_bytes(data)
    with database_connection(main_db) as connection:
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,current_root_kind='shared_workspace'
               WHERE family_id=?""",
            (central_relative, family_id),
        )

    result = synchronize_central_stock_projections(
        [main_db, other_db],
        workspace,
    )
    assert result["updated_file_count"] == 1
    with database_connection(other_db) as connection:
        after = connection.execute(
            "SELECT current_relative_path FROM files WHERE job_id='GLOBAL_RELEASE'"
        ).fetchone()
    assert str(after["current_relative_path"]) == central_relative


def test_0311_claim_reconcile_releases_stale_owned_claim_after_event_delete(tmp_path):
    database = tmp_path / "database" / "kamera.sqlite3"
    registry = tmp_path / "database" / "registry.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    layout = ensure_workspace_layout(workspace)
    initialize_database(database)
    initialize_library_registry(registry)
    adopt_main_library(
        registry,
        database_path=database,
        workspace_root=workspace,
        work_root=Path(layout["work_root"]),
        archive_root=archive,
    )

    create_job(
        database,
        job_id="CLAIM_RELEASE",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path=str(workspace / "SD-Kartensicherungen"),
        operation="folder_import",
    )
    family_id = _insert_family_file(
        database,
        job_id="CLAIM_RELEASE",
        family_key="claimed",
        relative_path="2026/2026-10-01/A.JPG",
        capture_time="2026-10-01T10:00:00",
        data=b"claim-release",
    )
    event = create_planned_event(
        database,
        "CLAIM_RELEASE",
        _preview(family_id, "2026-10-01", "Claim"),
    )
    event_id = str(event["parent_event"]["id"])
    with database_connection(database) as connection:
        connection.execute(
            "UPDATE events SET status='applied',applied_at=?,updated_at=? WHERE id=?",
            (NOW, NOW, event_id),
        )

    backfill_library_inventory(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
    )
    source_key = occurrence_key(MAIN_LIBRARY_ID, "CLAIM_RELEASE", "claimed")
    claim = get_source_family_claim(registry, source_key)
    assert claim is not None and claim["claim_state"] == "owned"

    with database_connection(database) as connection:
        connection.execute("DELETE FROM events WHERE id=?", (event_id,))

    state = backfill_library_claims(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
    )
    assert state == {
        "reserved_count": 0,
        "owned_count": 0,
        "claim_count": 0,
    }
    assert get_source_family_claim(registry, source_key) is None


def test_0311_central_sync_does_not_overwrite_locally_applied_path(tmp_path):
    main_db = tmp_path / "database" / "kamera.sqlite3"
    other_db = tmp_path / "database" / "business.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    initialize_database(main_db)
    initialize_database(other_db)

    create_job(
        main_db,
        job_id="OWNED_LOCAL",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path=str(workspace / "SD-Kartensicherungen"),
        operation="folder_import",
    )
    data = b"owned-local"
    _insert_family_file(
        main_db,
        job_id="OWNED_LOCAL",
        family_key="owned",
        relative_path="2026/2026-10-01/A.JPG",
        capture_time="2026-10-01T10:00:00",
        data=data,
    )
    project_import_job(main_db, other_db, "OWNED_LOCAL")

    with database_connection(other_db) as connection:
        family_id = int(connection.execute(
            "SELECT id FROM file_families WHERE job_id='OWNED_LOCAL'"
        ).fetchone()["id"])
    event = create_planned_event(
        other_db,
        "OWNED_LOCAL",
        _preview(family_id, "2026-10-01", "Business"),
    )
    event_id = str(event["parent_event"]["id"])
    local_path = "2026/10.01 - Business/Alle/A.JPG"
    with database_connection(other_db) as connection:
        connection.execute(
            "UPDATE events SET status='applied',applied_at=?,updated_at=? WHERE id=?",
            (NOW, NOW, event_id),
        )
        connection.execute(
            "UPDATE files SET current_relative_path=? WHERE family_id=?",
            (local_path, family_id),
        )

    central_relative = "2026/2026-10-01/A.JPG"
    central_file = workspace / "SD-Kartensicherungen" / central_relative
    central_file.parent.mkdir(parents=True, exist_ok=True)
    central_file.write_bytes(data)

    result = synchronize_central_stock_projections(
        [main_db, other_db],
        workspace,
    )
    with database_connection(other_db) as connection:
        after = connection.execute(
            "SELECT current_relative_path FROM files WHERE family_id=?",
            (family_id,),
        ).fetchone()
    assert str(after["current_relative_path"]) == local_path
