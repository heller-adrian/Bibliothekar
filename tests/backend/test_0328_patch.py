from __future__ import annotations

from pathlib import Path
import hashlib

from app import main, ui_shell
from app.database import (
    create_planned_event,
    database_connection,
    initialize_database,
)
from app.library_registry import (
    MAIN_LIBRARY_ID,
    adopt_main_library,
    get_library,
    initialize_library_registry,
    update_library_paths,
)
from app.sort_plan import build_event_sort_plan
from app.workspace_layout import ensure_workspace_layout


def test_0328_fresh_workspace_uses_single_managed_root(tmp_path: Path, monkeypatch):
    config = tmp_path / "config" / "settings.json"
    monkeypatch.setenv("KAMERA_CONFIG", str(config))

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_workspace_layout(workspace)

    assert Path(layout["backup_root"]) == workspace / "SD-Kartensicherungen"
    assert Path(layout["workspaces_root"]) == workspace / "Arbeitsbereiche"
    assert Path(layout["metadata_root"]) == workspace / "Metadatenkorrektur"
    assert Path(layout["work_root"]) == workspace / "Arbeitsbereiche" / "main"

    # Der alte interne Name bleibt nur als transparenter Kompatibilitätsalias.
    legacy = workspace / "Arbeitsbereich"
    assert legacy.is_symlink()
    assert legacy.resolve() == Path(layout["work_root"]).resolve()


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

    assert main.DEPLOYMENT_VERSION == "0.32.8"
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
