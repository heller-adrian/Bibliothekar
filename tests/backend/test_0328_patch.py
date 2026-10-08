from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from app import main, ui_shell
from app.database import (
    create_planned_event,
    database_connection,
    initialize_database,
)
from app.library_registry import (
    MAIN_LIBRARY_ID,
    adopt_main_library,
    LibraryRegistryError,
    ensure_library_identity,
    get_library,
    initialize_library_registry,
    register_library,
    update_library_paths,
)
from app.global_library_inventory import backfill_library_inventory
from app.global_stock import migrate_main_free_stock_to_central
from app.sort_plan import build_event_sort_plan
from app.workspace_layout import ensure_workspace_layout, resolve_library_work_root


def test_0328_fresh_workspace_uses_single_managed_root(tmp_path: Path, monkeypatch):
    config = tmp_path / "config" / "settings.json"
    monkeypatch.setenv("KAMERA_CONFIG", str(config))

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_workspace_layout(workspace)

    assert Path(layout["backup_root"]) == workspace / "SD-Kartensicherungen"
    assert Path(layout["workspaces_root"]) == workspace / "Arbeitsbereiche"
    assert Path(layout["metadata_root"]) == workspace / "Metadatenkorrektur"
    assert Path(layout["work_root"]) == workspace / "Arbeitsbereiche"
    assert not (workspace / "Arbeitsbereiche" / "main").exists()

    # Vor der ersten Bibliothek gibt es keinen Bibliotheks-Unterordner.
    # Der historische Singular-Pfad darf nur auf den neutralen Stamm zeigen.
    legacy = workspace / "Arbeitsbereich"
    assert legacy.is_symlink()
    assert legacy.resolve() == (workspace / "Arbeitsbereiche").resolve()


def test_0328_main_archive_path_survives_bootstrap_adoption(tmp_path: Path):
    database = tmp_path / "db" / "kamera.sqlite3"
    registry = tmp_path / "db" / "registry.sqlite3"
    workspace = tmp_path / "workspace"
    archive_initial = tmp_path / "archive-initial"
    archive_selected = tmp_path / "archive-selected"
    archive_environment = tmp_path / "archive-environment"

    workspace.mkdir()
    archive_initial.mkdir()
    archive_selected.mkdir()
    archive_environment.mkdir()
    initialize_database(database)
    initialize_library_registry(registry)

    adopt_main_library(
        registry,
        database_path=database,
        workspace_root=workspace,
        work_root=workspace / "Arbeitsbereiche" / "main",
        archive_root=archive_initial,
    )
    update_library_paths(
        registry,
        MAIN_LIBRARY_ID,
        archive_root=archive_selected,
    )

    # Ein späterer Prozessstart darf die vom Nutzer gespeicherte Auswahl nicht
    # wieder mit dem Container-Bootstrapwert überschreiben.
    adopt_main_library(
        registry,
        database_path=database,
        workspace_root=workspace,
        work_root=workspace / "Arbeitsbereiche" / "main",
        archive_root=archive_environment,
    )
    stored = get_library(registry, MAIN_LIBRARY_ID, active_only=False)
    assert stored is not None
    assert Path(str(stored["archive_root"])) == archive_selected.resolve()


def test_0328_schema_persists_archive_and_sort_source_provenance(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)

    with database_connection(database) as connection:
        asset_columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(event_change_asset_reviews)"
            ).fetchall()
        }
        sort_columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(sort_operations)"
            ).fetchall()
        }
        sort_asset_columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(sort_asset_operations)"
            ).fetchall()
        }

    assert {
        "source_root_kind",
        "workspace_original_path",
        "workspace_staging_path",
        "released_archive_asset_id",
    } <= asset_columns
    assert "source_root_path" in sort_columns
    assert "source_root_path" in sort_asset_columns


def test_0328_settings_surface_exposes_paths_and_editable_library_roots():
    shell = ui_shell._shell_markup("workspace", "events")
    script = ui_shell.BIBLIOTHEKAR_JS

    assert main.DEPLOYMENT_VERSION == "0.44.1"
    assert 'data-bk-settings-area="paths"' in shell
    assert 'id="bk-storage-backup-name"' in shell
    assert 'id="bk-storage-workspaces-name"' in shell
    assert 'id="bk-storage-metadata-name"' in shell
    assert 'data-bk-library-work' in script
    assert 'data-bk-library-archive' in script
    assert "/api/settings/storage-paths" in script
    assert "Hardlinks zum Zentralbestand möglich" in script



def _sha_0328(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_0328_released_stock_sort_plan_uses_13_files_without_legacy_job_blockers(
    tmp_path: Path,
    monkeypatch,
):
    config = tmp_path / "config" / "settings.json"
    monkeypatch.setenv("KAMERA_CONFIG", str(config))
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    initialize_database(database)

    job_id = "RELEASED_13"
    family_ids: list[int] = []
    source_file_ids: list[int] = []
    central = workspace / "SD-Kartensicherungen"
    released_dir = (
        central
        / "Freigewordene Archivdateien"
        / "2026"
        / "2026-07-19"
    )
    released_dir.mkdir(parents=True, exist_ok=True)

    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   working_path,source_path,created_at,updated_at
               ) VALUES (
                   ?, 'sd_import','manual','completed','done','folder_import',?,
                   '/nicht-mehr-vorhanden','/nicht-mehr-vorhanden',?,?
               )""",
            (job_id, job_id, "2026-10-02T19:00:00+00:00", "2026-10-02T19:00:00+00:00"),
        )
        for index, minute in enumerate((1, 15, 25, 40, 58), start=1):
            capture = f"2026-07-19T19:{minute:02d}:00"
            stem = f"20260719_19{minute:02d}00_Fuji-X-E5"
            family_id = int(
                connection.execute(
                    """INSERT INTO file_families(
                           job_id,family_key,original_stem,status,
                           selected_capture_time,capture_time_confidence
                       ) VALUES (?,?,?,'complete',?,'high')""",
                    (job_id, f"F{index}", stem, capture),
                ).lastrowid
            )
            family_ids.append(family_id)
            connection.execute(
                """INSERT INTO released_free_families(
                       job_id,family_id,released_start_datetime,
                       released_end_datetime,created_at,archive_origin
                   ) VALUES (?,?,?,?,?,1)""",
                (
                    job_id,
                    family_id,
                    "2026-07-19T19:01:00",
                    "2026-07-19T23:59:59",
                    "2026-10-02T19:00:00+00:00",
                ),
            )
            jpg_id = None
            for extension, media_type in ((".JPG", "jpeg"), (".RAF", "raw")):
                relative = (
                    "Freigewordene Archivdateien/2026/2026-07-19/"
                    + stem
                    + extension
                )
                payload = f"{extension}-{index}".encode()
                digest = _sha_0328(payload)
                file_id = int(
                    connection.execute(
                        """INSERT INTO files(
                               job_id,family_id,original_relative_path,
                               current_relative_path,original_filename,
                               extension,media_type,size_bytes,
                               sha256_original,sha256_current,
                               selected_capture_time,selected_capture_source,
                               capture_time_confidence,review_status,
                               metadata_write_status,current_root_kind,
                               created_at,updated_at
                           ) VALUES (
                               ?,?,?,?,?,?,?,?,?,?,?,?,'high','not_required',
                               'not_requested','shared_workspace',?,?
                           )""",
                        (
                            job_id,
                            family_id,
                            relative,
                            relative,
                            Path(relative).name,
                            extension,
                            media_type,
                            len(payload),
                            digest,
                            digest,
                            capture,
                            "DateTimeOriginal",
                            "2026-10-02T19:00:00+00:00",
                            "2026-10-02T19:00:00+00:00",
                        ),
                    ).lastrowid
                )
                if extension == ".JPG":
                    jpg_id = file_id
                (central / relative).write_bytes(payload)
            assert jpg_id is not None
            source_file_ids.append(jpg_id)

        for family_index, kind, filename, payload in (
            (0, "xmp", "20260719_190100_Fuji-X-E5.xmp", b"xmp-one"),
            (2, "xmp", "20260719_192500_Fuji-X-E5.xmp", b"xmp-two"),
            (2, "export", "20260719_192500_Fuji-X-E5_Export.jpg", b"export-one"),
        ):
            relative = (
                "Freigewordene Archivdateien/2026/2026-07-19/"
                + filename
            )
            connection.execute(
                """INSERT INTO released_archive_assets(
                       job_id,family_id,source_file_id,asset_kind,
                       current_relative_path,size_bytes,sha256,
                       origin_change_request_id,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    job_id,
                    family_ids[family_index],
                    source_file_ids[family_index],
                    kind,
                    relative,
                    len(payload),
                    _sha_0328(payload),
                    "CR_RELEASE",
                    "2026-10-02T19:00:00+00:00",
                    "2026-10-02T19:00:00+00:00",
                ),
            )
            (central / relative).write_bytes(payload)

    preview = {
        "event_kind": "event",
        "event_name": "Test fA",
        "start_date": "2026-07-19",
        "end_date": "2026-07-19",
        "start_time": "19:01",
        "end_time": "23:59",
        "uses_time_range": True,
        "preserve_day_folders": False,
        "parent_folder": "07-19 - Test fA",
        "child_folder": None,
        "child_event_name": None,
        "selected_day_keys": ["2026-07-19"],
        "selected_family_ids": family_ids,
        "structure_lines": [],
    }
    created = create_planned_event(database, job_id, preview)
    event_id = str(created["parent_event"]["id"])

    plan = build_event_sort_plan(
        database,
        job_id,
        event_id,
        workspace,
        verify_sha256=True,
    )

    assert plan["summary"]["family_count"] == 5
    assert plan["summary"]["camera_file_count"] == 10
    assert plan["summary"]["asset_count"] == 3
    assert plan["summary"]["file_count"] == 13
    assert plan["summary"]["blocker_count"] == 0, plan["blockers"]
    assert plan["summary"]["ready"] is True
    assert {
        Path(item["source_root_path"]).resolve()
        for item in [*plan["files"], *plan["assets"]]
    } == {central.resolve()}



def test_0328_managed_workspaces_name_change_retargets_main_alias_and_registry(
    tmp_path: Path,
    monkeypatch,
):
    config = tmp_path / "config" / "settings.json"
    monkeypatch.setenv("KAMERA_CONFIG", str(config))

    workspace = tmp_path / "workspace"
    database_dir = tmp_path / "database"
    database = database_dir / "kamera.sqlite3"
    registry = database_dir / "registry.sqlite3"
    archive = tmp_path / "archive"
    workspace.mkdir()
    database_dir.mkdir()
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

    monkeypatch.setattr(main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)

    result = main.api_set_storage_paths({
        "backup_directory_name": "SD-Kartensicherungen",
        "workspaces_directory_name": "Bibliotheksbereiche",
        "metadata_directory_name": "Metadatenkorrektur",
    })

    canonical = workspace / "Bibliotheksbereiche"
    legacy = workspace / "Arbeitsbereich"
    stored = get_library(registry, MAIN_LIBRARY_ID, active_only=False)

    assert Path(result["workspaces_root"]) == canonical
    assert canonical.is_dir()
    assert not (canonical / "main").exists()
    assert not (workspace / "Arbeitsbereiche").exists()
    assert legacy.is_symlink()
    assert legacy.resolve() == canonical.resolve()
    assert stored is not None
    assert Path(str(stored["work_root"])) == canonical.resolve()



def _insert_0328_inventory_fixture(database: Path, job_id: str = "SHARED_JOB") -> None:
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,
                   source_volume_label,source_signature,source_path,
                   created_at,updated_at
               ) VALUES (
                   ?,'sd_import','manual','completed','done','folder_import',
                   'Shared','same-signature','/shared/source',?,?
               )""",
            (
                job_id,
                "2026-10-02T20:00:00+00:00",
                "2026-10-02T20:00:00+00:00",
            ),
        )
        family_id = int(
            connection.execute(
                """INSERT INTO file_families(
                       job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence
                   ) VALUES (?,?,?,'complete',?,'high')""",
                (
                    job_id,
                    "FAMILY",
                    "20260719_190100_Fuji-X-E5",
                    "2026-07-19T19:01:00",
                ),
            ).lastrowid
        )
        payload = b"same-source"
        digest = hashlib.sha256(payload).hexdigest()
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,
                   current_relative_path,original_filename,
                   extension,media_type,size_bytes,
                   sha256_original,sha256_current,
                   selected_capture_time,selected_capture_source,
                   capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,
                   created_at,updated_at
               ) VALUES (
                   ?,?,?,?,?,?,?,?,?,?,?,?,'high','not_required',
                   'not_requested','shared_workspace',?,?
               )""",
            (
                job_id,
                family_id,
                "2026-07-19/photo.JPG",
                "2026-07-19/photo.JPG",
                "photo.JPG",
                ".JPG",
                "jpeg",
                len(payload),
                digest,
                digest,
                "2026-07-19T19:01:00",
                "DateTimeOriginal",
                "2026-10-02T20:00:00+00:00",
                "2026-10-02T20:00:00+00:00",
            ),
        )
        connection.commit()


def test_0328_two_library_inventory_backfills_do_not_collide_on_source_backup(
    tmp_path: Path,
):
    registry = tmp_path / "registry.sqlite3"
    main_db = tmp_path / "kamera.sqlite3"
    test_db = tmp_path / "libraries" / "test.sqlite3"
    workspace = tmp_path / "workspace"
    main_archive = tmp_path / "main-archive"
    test_archive = tmp_path / "test-archive"
    main_work = workspace / "Arbeitsbereiche" / "Arbeitsbereich"
    test_work = workspace / "Arbeitsbereiche" / "Testarbeitsbereich"

    for path in (workspace, main_archive, test_archive, main_work, test_work):
        path.mkdir(parents=True, exist_ok=True)
    initialize_database(main_db)
    initialize_database(test_db)
    ensure_library_identity(main_db, MAIN_LIBRARY_ID)
    ensure_library_identity(test_db, "test")
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id=MAIN_LIBRARY_ID,
        display_name="Main",
        database_path=main_db,
        workspace_root=workspace,
        work_root=main_work,
        archive_root=main_archive,
        is_main=True,
        is_active=True,
    )
    register_library(
        registry,
        library_id="test",
        display_name="Test",
        database_path=test_db,
        workspace_root=workspace,
        work_root=test_work,
        archive_root=test_archive,
        is_main=False,
        is_active=True,
    )

    _insert_0328_inventory_fixture(main_db)
    _insert_0328_inventory_fixture(test_db)

    main_result = backfill_library_inventory(
        registry,
        database_path=main_db,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )
    test_result = backfill_library_inventory(
        registry,
        database_path=test_db,
        library_id="test",
        claim_all_owned=False,
    )

    assert main_result["family_count"] == 1
    assert test_result["family_count"] == 1
    with database_connection(registry) as connection:
        backups = [
            dict(row)
            for row in connection.execute(
                """SELECT backup_id,source_kind,source_identity,backup_path
                   FROM source_backups
                   ORDER BY backup_id"""
            ).fetchall()
        ]
        canonical = connection.execute(
            "SELECT COUNT(*) AS n FROM canonical_families"
        ).fetchone()
    assert backups == [
        {
            "backup_id": "main:SHARED_JOB",
            "source_kind": "import",
            "source_identity": "same-signature",
            "backup_path": "/shared/source",
        },
        {
            "backup_id": "test:SHARED_JOB",
            "source_kind": "existing_library",
            "source_identity": "test:same-signature",
            "backup_path": "/shared/source",
        },
    ]
    assert int(canonical["n"]) == 1


def test_0328_registered_database_path_repairs_only_matching_canonical_db(
    tmp_path: Path,
    monkeypatch,
):
    database_dir = tmp_path / "database"
    registry = database_dir / "bibliothekar-global.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereiche" / "Testarbeitsbereich"
    archive = tmp_path / "archive"
    canonical = database_dir / "libraries" / "test.sqlite3"
    stale = tmp_path / "old-location" / "test.sqlite3"

    work.mkdir(parents=True)
    archive.mkdir()
    initialize_database(canonical)
    ensure_library_identity(canonical, "test")
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id="test",
        display_name="Test",
        database_path=stale,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=False,
        is_active=False,
    )

    monkeypatch.setattr(main, "DATABASE_DIRECTORY", database_dir)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)

    row = get_library(registry, "test", active_only=False)
    assert row is not None
    resolved, repaired = main._resolve_registered_library_database(row)

    assert resolved == canonical.resolve()
    assert Path(str(repaired["database_path"])) == canonical.resolve()
    stored = get_library(registry, "test", active_only=False)
    assert stored is not None
    assert Path(str(stored["database_path"])) == canonical.resolve()


def test_0328_missing_secondary_database_is_not_silently_recreated(
    tmp_path: Path,
    monkeypatch,
):
    database_dir = tmp_path / "database"
    registry = database_dir / "bibliothekar-global.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereiche" / "Testarbeitsbereich"
    archive = tmp_path / "archive"
    missing = database_dir / "libraries" / "test.sqlite3"

    work.mkdir(parents=True)
    archive.mkdir()
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id="test",
        display_name="Test",
        database_path=missing,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=False,
        is_active=False,
    )

    monkeypatch.setattr(main, "DATABASE_DIRECTORY", database_dir)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)

    row = get_library(registry, "test", active_only=False)
    assert row is not None
    with pytest.raises(LibraryRegistryError, match="SQLite-Datenbank"):
        main._resolve_registered_library_database(row)
    assert not missing.exists()



def test_0328_legacy_main_existing_library_is_upgraded_to_import(
    tmp_path: Path,
):
    registry = tmp_path / "registry.sqlite3"
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    work = workspace / "Arbeitsbereiche" / "Arbeitsbereich"

    work.mkdir(parents=True)
    archive.mkdir()
    initialize_database(database)
    ensure_library_identity(database, MAIN_LIBRARY_ID)
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id=MAIN_LIBRARY_ID,
        display_name="Main",
        database_path=database,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=True,
        is_active=True,
    )
    _insert_0328_inventory_fixture(database)

    with database_connection(registry) as connection:
        connection.execute(
            """INSERT INTO source_backups(
                   backup_id,source_kind,source_identity,backup_path,
                   metadata_json,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                "main:SHARED_JOB",
                "existing_library",
                "same-signature",
                "/shared/source",
                "{}",
                "2026-10-02T19:00:00+00:00",
                "2026-10-02T19:00:00+00:00",
            ),
        )
        connection.commit()

    result = backfill_library_inventory(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )

    assert result["family_count"] == 1
    with database_connection(registry) as connection:
        row = connection.execute(
            """SELECT source_kind,source_identity,backup_path
               FROM source_backups
               WHERE backup_id='main:SHARED_JOB'"""
        ).fetchone()
    assert row is not None
    assert str(row["source_kind"]) == "import"
    assert str(row["source_identity"]) == "same-signature"
    assert str(row["backup_path"]) == "/shared/source"



def test_0328_failed_library_creation_removes_registry_zombie_and_new_db(
    tmp_path: Path,
    monkeypatch,
):
    database_dir = tmp_path / "database"
    registry = database_dir / "bibliothekar-global.sqlite3"
    main_db = database_dir / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereiche" / "new-library"
    archive = tmp_path / "archive"

    database_dir.mkdir()
    workspace.mkdir()
    work.mkdir(parents=True)
    archive.mkdir()
    initialize_database(main_db)
    initialize_library_registry(registry)

    monkeypatch.setattr(main, "DATABASE_DIRECTORY", database_dir)
    monkeypatch.setattr(main, "DATABASE_FILE", main_db)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
    monkeypatch.setattr(main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(
        main,
        "inspect_library_paths",
        lambda *args, **kwargs: {
            "valid": True,
            "work_root": str(work),
            "archive_root": str(archive),
            "managed_default_work_root": False,
            "errors": [],
            "warnings": [],
        },
    )

    def fail_backfill(*args, **kwargs):
        raise RuntimeError("simulierter Inventory-Fehler")

    monkeypatch.setattr(main, "backfill_library_inventory", fail_backfill)

    with pytest.raises(main.HTTPException, match="simulierter Inventory-Fehler"):
        main.api_create_library(
            {
                "display_name": "Fehlgeschlagen",
                "work_root": str(work),
                "archive_root": str(archive),
            }
        )

    with database_connection(registry) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS n FROM libraries"
        ).fetchone()
    assert int(count["n"]) == 0
    assert list((database_dir / "libraries").glob("*.sqlite3")) == []



def test_0328_explicit_library_work_root_does_not_require_default_main(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    workspaces = workspace / "Arbeitsbereiche"
    custom_main = workspaces / "Arbeitsbereich"
    workspace.mkdir()
    custom_main.mkdir(parents=True)

    # Exakter Fehlerfall aus dem Clean-Slate-Test: der historische Alias zeigt
    # noch auf den inzwischen entfernten Erstinstallations-Standard "main".
    (workspace / "Arbeitsbereich").symlink_to(
        workspaces / "main",
        target_is_directory=True,
    )

    resolved = resolve_library_work_root(
        workspace,
        custom_main,
    )

    assert resolved == custom_main.resolve()
    assert not (workspaces / "main").exists()


def test_0328_registered_main_workspace_retargets_alias_without_recreating_main(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    workspaces = workspace / "Arbeitsbereiche"
    custom_main = workspaces / "Arbeitsbereich"
    workspace.mkdir()
    custom_main.mkdir(parents=True)

    legacy = workspace / "Arbeitsbereich"
    legacy.symlink_to(
        workspaces / "main",
        target_is_directory=True,
    )

    layout = ensure_workspace_layout(
        workspace,
        configured_main_work_root=custom_main,
    )

    assert Path(layout["work_root"]) == custom_main.resolve()
    assert legacy.is_symlink()
    assert legacy.resolve() == custom_main.resolve()
    assert not (workspaces / "main").exists()


def test_0328_global_stock_migration_uses_registered_main_workspace(
    tmp_path: Path,
    monkeypatch,
):
    config = tmp_path / "config" / "settings.json"
    monkeypatch.setenv("KAMERA_CONFIG", str(config))

    workspace = tmp_path / "workspace"
    custom_main = workspace / "Arbeitsbereiche" / "Arbeitsbereich"
    database = tmp_path / "kamera.sqlite3"
    workspace.mkdir()
    custom_main.mkdir(parents=True)
    initialize_database(database)

    # Kein /Arbeitsbereiche/main und kein funktionierender Legacy-Alias nötig.
    result = migrate_main_free_stock_to_central(
        database,
        workspace,
        main_work_root=custom_main,
    )

    assert result["migrated"] == 0
    assert result["already_migrated"] == 0
    assert not (workspace / "Arbeitsbereiche" / "main").exists()


def test_0328_main_path_edit_retargets_legacy_alias_to_saved_path(
    tmp_path: Path,
    monkeypatch,
):
    database_dir = tmp_path / "database"
    database = database_dir / "kamera.sqlite3"
    registry = database_dir / "registry.sqlite3"
    workspace = tmp_path / "workspace"
    default_main = workspace / "Arbeitsbereiche" / "main"
    custom_main = workspace / "Arbeitsbereiche" / "Arbeitsbereich"
    archive = tmp_path / "archive"

    database_dir.mkdir()
    workspace.mkdir()
    default_main.mkdir(parents=True)
    custom_main.mkdir(parents=True)
    archive.mkdir()
    initialize_database(database)
    initialize_library_registry(registry)
    adopt_main_library(
        registry,
        database_path=database,
        workspace_root=workspace,
        work_root=default_main,
        archive_root=archive,
    )

    legacy = workspace / "Arbeitsbereich"
    legacy.symlink_to(default_main, target_is_directory=True)

    monkeypatch.setattr(main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
    monkeypatch.setattr(
        main,
        "inspect_library_paths",
        lambda *args, **kwargs: {
            "valid": True,
            "work_root": str(custom_main),
            "archive_root": str(archive),
            "managed_default_work_root": False,
            "archive_read_only": True,
            "hardlink_to_central_stock": True,
            "errors": [],
            "warnings": [],
        },
    )

    result = main.api_update_library(
        MAIN_LIBRARY_ID,
        {
            "work_root": str(custom_main),
            "archive_root": str(archive),
        },
    )

    stored = get_library(registry, MAIN_LIBRARY_ID, active_only=False)
    assert stored is not None
    assert Path(str(stored["work_root"])) == custom_main.resolve()
    assert Path(str(result["library"]["work_root"])) == custom_main.resolve()
    assert legacy.is_symlink()
    assert legacy.resolve() == custom_main.resolve()
