from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from app import main, ui_shell
from app.database import (
    claim_next_job,
    create_job,
    database_connection,
    get_job,
    initialize_database,
)
from app.global_library_inventory import (
    backfill_library_inventory,
    blocked_family_ids,
    promote_family_ids_owned,
    reserve_family_ids,
)
from app.global_stock import project_import_job
from app.library_context import LibraryContext
from app.library_registry import (
    MAIN_LIBRARY_ID,
    LibraryRegistryError,
    adopt_main_library,
    ensure_library_identity,
    get_source_family_claim,
    initialize_library_registry,
    register_library,
    register_source_backup,
    register_source_family,
)


NOW = "2026-10-02T00:00:00+00:00"


def _insert_family(
    database: Path,
    *,
    job_id: str,
    family_key: str,
    relative_path: str,
    data: bytes,
) -> int:
    digest = hashlib.sha256(data).hexdigest()
    with database_connection(database) as connection:
        cursor = connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?, ?, ?, 'complete', '2026-10-02T10:00:00', 'high')""",
            (job_id, family_key, family_key),
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
               VALUES (?, ?, ?, ?, ?, '.JPG', 'jpeg', ?, ?, ?,
                       '2026-10-02T10:00:00', 'qa', 'high', 'not_required',
                       'not_requested', 'shared_workspace', ?, ?)""",
            (
                job_id,
                family_id,
                relative_path,
                relative_path,
                Path(relative_path).name,
                len(data),
                digest,
                digest,
                NOW,
                NOW,
            ),
        )
    return family_id


def test_0322_operation_scoped_claim_selects_global_folder_import(tmp_path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)

    create_job(
        database,
        job_id="SIM_FIRST",
        kind="simulation",
        trigger_type="manual",
        operation="sd_lifecycle_simulation",
    )
    create_job(
        database,
        job_id="FOLDER_IMPORT",
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
    )

    claimed = claim_next_job(database, operation="folder_import")

    assert claimed is not None
    assert claimed["id"] == "FOLDER_IMPORT"
    assert claimed["state"] == "copying"
    assert get_job(database, "SIM_FIRST")["state"] == "queued"


def test_0322_worker_claims_global_import_before_library_registry_queue(
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    initialize_database(database)
    create_job(
        database,
        job_id="GLOBAL_FOLDER_IMPORT",
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
    )

    context = LibraryContext(
        library_id=MAIN_LIBRARY_ID,
        display_name="Main Library",
        database_path=database,
        workspace_root=workspace,
        work_root=workspace / "Arbeitsbereich",
        archive_root=archive,
        is_main=True,
        settings={},
    )
    processed: list[tuple[str, str]] = []

    monkeypatch.setattr(main, "DATABASE_FILE", database)
    monkeypatch.setattr(main, "MAIN_LIBRARY_CONTEXT", context)
    from app.library_registry import initialize_library_registry
    registry=tmp_path/'registry.sqlite3';initialize_library_registry(registry)
    monkeypatch.setattr(main,'REGISTRY_DATABASE_FILE',registry)
    monkeypatch.setattr(main,'WORKSPACE_PATH',workspace)
    monkeypatch.setattr(main,'build_main_library_context',lambda:context)
    # A rejected admission must terminate this test instead of hiding its cause.
    retries=[]
    def bounded_wait(seconds):
        retries.append(seconds);main.WORKER_STOP.set();return True
    monkeypatch.setattr(main.WORKER_STOP,'wait',bounded_wait)


    def registry_must_not_be_needed(_registry):
        raise AssertionError("Globaler Folder-Import darf nicht von Registry-Queues abhängen.")

    monkeypatch.setattr(main, "list_active_library_contexts", registry_must_not_be_needed)

    def fake_process(job, *, library_context=None):
        processed.append((str(job["id"]), str(library_context.library_id)))
        main.WORKER_STOP.set()

    monkeypatch.setattr(main, "process_claimed_job", fake_process)
    main.WORKER_STOP.clear()
    try:
        main.worker_loop()
    finally:
        main.WORKER_STOP.clear()

    assert not retries, "Worker admission unexpectedly rejected the bounded fixture"
    assert processed == [("GLOBAL_FOLDER_IMPORT", MAIN_LIBRARY_ID)]
    assert get_job(database, "GLOBAL_FOLDER_IMPORT")["state"] == "copying"


def test_0322_planning_reservation_is_globally_exclusive(tmp_path):
    main_db = tmp_path / "database" / "main.sqlite3"
    second_db = tmp_path / "database" / "second.sqlite3"
    registry = tmp_path / "database" / "registry.sqlite3"
    workspace = tmp_path / "workspace"
    main_work = tmp_path / "main-work"
    second_work = tmp_path / "second-work"
    main_archive = tmp_path / "main-archive"
    second_archive = tmp_path / "second-archive"
    for path in (workspace, main_work, second_work, main_archive, second_archive):
        path.mkdir(parents=True, exist_ok=True)

    initialize_database(main_db)
    initialize_database(second_db)
    initialize_library_registry(registry)
    adopt_main_library(
        registry,
        database_path=main_db,
        workspace_root=workspace,
        work_root=main_work,
        archive_root=main_archive,
    )
    ensure_library_identity(second_db, "second")
    register_library(
        registry,
        library_id="second",
        display_name="Second",
        database_path=second_db,
        workspace_root=workspace,
        work_root=second_work,
        archive_root=second_archive,
        is_main=False,
        is_active=True,
    )

    for database in (main_db, second_db):
        create_job(
            database,
            job_id="GLOBAL_IMPORT",
            kind="sd_import",
            trigger_type="manual",
            operation="folder_import",
            source_path="/source",
            working_path="/workspace/SD-Kartensicherungen",
        )

    main_family = _insert_family(
        main_db,
        job_id="GLOBAL_IMPORT",
        family_key="same-family",
        relative_path="2026/2026-10-02/A.JPG",
        data=b"same-content",
    )
    second_family = _insert_family(
        second_db,
        job_id="GLOBAL_IMPORT",
        family_key="same-family",
        relative_path="2026/2026-10-02/A.JPG",
        data=b"same-content",
    )

    for library_id, source_identity in (
        (MAIN_LIBRARY_ID, "main-source"),
        ("second", "second-source"),
    ):
        backup_id = f"{library_id}:GLOBAL_IMPORT"
        register_source_backup(
            registry,
            backup_id=backup_id,
            source_kind="existing_library",
            source_identity=source_identity,
            backup_path=f"/source/{library_id}",
            metadata={"library_id": library_id, "job_id": "GLOBAL_IMPORT"},
        )
        register_source_family(
            registry,
            source_family_key=f"{library_id}:GLOBAL_IMPORT:same-family",
            backup_id=backup_id,
            family_key="same-family",
            content_fingerprint="family-members-sha256:0322-same-family",
            metadata={"library_id": library_id, "job_id": "GLOBAL_IMPORT"},
        )

    reserve_family_ids(
        registry,
        database_path=main_db,
        library_id=MAIN_LIBRARY_ID,
        event_id="main-planned",
        family_ids=[main_family],
    )

    assert blocked_family_ids(
        registry,
        database_path=second_db,
        library_id="second",
    ) == {second_family}

    with pytest.raises(LibraryRegistryError):
        reserve_family_ids(
            registry,
            database_path=second_db,
            library_id="second",
            event_id="second-planned",
            family_ids=[second_family],
        )

    promote_family_ids_owned(
        registry,
        database_path=main_db,
        library_id=MAIN_LIBRARY_ID,
        event_id="main-applied",
        family_ids=[main_family],
    )

    assert blocked_family_ids(
        registry,
        database_path=second_db,
        library_id="second",
    ) == {second_family}

    second_source_key = f"second:GLOBAL_IMPORT:same-family"
    effective = get_source_family_claim(registry, second_source_key)
    assert effective is not None
    assert effective["claim_state"] == "owned"
    assert effective["library_id"] == MAIN_LIBRARY_ID

    with pytest.raises(LibraryRegistryError):
        promote_family_ids_owned(
            registry,
            database_path=second_db,
            library_id="second",
            event_id="second-applied",
            family_ids=[second_family],
        )


def test_0322_settings_are_wide_scrollable_and_library_add_is_collapsed():
    shell = ui_shell._shell_markup("workspace", "captures")
    css = ui_shell.BIBLIOTHEKAR_0311_CSS

    assert "width: min(880px, calc(100vw - 28px))" in css
    assert "flex-wrap: nowrap" in css
    assert "overflow-x: auto" in css
    assert "grid-template-columns: repeat(2" not in css
    assert "min-width: max-content" in css
    assert "overflow-y: auto" in css

    assert '<details class="bk-library-add-card">' in shell
    assert '<details class="bk-library-add-card" open' not in shell
    assert "<summary>Bibliothek hinzufügen</summary>" in shell
