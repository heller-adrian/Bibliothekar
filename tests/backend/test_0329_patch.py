from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app import main
from app.database import (
    create_planned_event,
    database_connection,
    get_event_edit_context,
    initialize_database,
)
from app.global_workspace import build_global_workspace_summary
from app.library_context import LibraryContext
from app.library_registry import (
    MAIN_LIBRARY_ID,
    get_library,
    initialize_library_registry,
)
from app.planning import list_job_planning_overview
from app.sort_plan import build_event_sort_plan
from app.workspace_layout import (
    WorkspaceLayoutError,
    ensure_workspace_layout,
    resolve_library_work_root,
)


NOW = "2026-10-02T20:30:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed_19_file_free_day(
    database: Path,
    workspace: Path,
) -> tuple[str, list[int]]:
    job_id = "FREE_19"
    central = workspace / "SD-Kartensicherungen"
    day_root = central / "2026" / "2026-07-19"
    day_root.mkdir(parents=True, exist_ok=True)
    family_ids: list[int] = []

    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   working_path,source_path,created_at,updated_at
               ) VALUES (
                   ?,'sd_import','manual','completed','done','folder_import',?,
                   ?,?, ?,?
               )""",
            (
                job_id,
                "Clean-Slate",
                str(central),
                "/nicht-mehr-relevant",
                NOW,
                NOW,
            ),
        )

        stems: list[str] = []
        for index, minute in enumerate((11, 32, 51, 25, 31, 45, 8, 58), start=1):
            capture = f"2026-07-19T{17 + (index // 4):02d}:{minute:02d}:00"
            stem = f"20260719_{capture[11:13]}{minute:02d}00_Fuji-X-E5"
            stems.append(stem)
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

            for extension, media_type in ((".JPG", "jpeg"), (".RAF", "raw")):
                relative = f"2026/2026-07-19/{stem}{extension}"
                payload = f"{index}-{extension}".encode()
                digest = _sha(payload)
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
                        NOW,
                        NOW,
                    ),
                )
                (central / relative).write_bytes(payload)

    # Genau der manuelle Testfall: 16 importierte Kameraoriginale und drei
    # später physisch hinzugekommene, noch nicht in SQLite erfasste Dateien.
    loose = (
        (stems[0] + ".xmp", b"xmp-one"),
        (stems[1] + ".xmp", b"xmp-two"),
        (stems[0] + "_Export.jpg", b"export-one"),
    )
    for filename, payload in loose:
        (day_root / filename).write_bytes(payload)

    return job_id, family_ids


def _planned_event(database: Path, job_id: str, family_ids: list[int]) -> str:
    preview = {
        "event_kind": "event",
        "event_name": "Test 6",
        "start_date": "2026-07-19",
        "end_date": "2026-07-19",
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "parent_folder": "07-19 - Test 6",
        "child_folder": None,
        "child_event_name": None,
        "selected_day_keys": ["2026-07-19"],
        "selected_family_ids": family_ids,
        "structure_lines": [],
    }
    created = create_planned_event(database, job_id, preview)
    return str(created["parent_event"]["id"])


def test_0329_clean_workspace_has_no_automatic_main_folder(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    layout = ensure_workspace_layout(
        workspace,
        create_default_main=False,
    )

    assert Path(layout["work_root"]) == workspace / "Arbeitsbereiche"
    assert (workspace / "Arbeitsbereiche").is_dir()
    assert (workspace / "SD-Kartensicherungen").is_dir()
    assert (workspace / "Metadatenkorrektur").is_dir()
    assert not (workspace / "Arbeitsbereiche" / "main").exists()
    assert not (workspace / "Arbeitsbereich").exists()


def test_0329_main_is_never_created_even_by_legacy_default_or_missing_saved_path(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Selbst ein alter Aufrufer, der den früheren Schalter noch setzt, darf
    # keinen /Arbeitsbereiche/main-Ordner erzeugen.
    layout = ensure_workspace_layout(
        workspace,
        create_default_main=True,
    )
    main_path = workspace / "Arbeitsbereiche" / "main"
    assert Path(layout["work_root"]) == workspace / "Arbeitsbereiche"
    assert not main_path.exists()

    # Auch ein veralteter gespeicherter Main-Pfad wird niemals still neu
    # materialisiert. Der Nutzerpfad bleibt die einzige Quelle der Wahrheit.
    with pytest.raises(WorkspaceLayoutError):
        resolve_library_work_root(workspace, main_path)
    assert not main_path.exists()


def test_0329_first_library_is_user_named_primary_without_main_work_folder(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    database_dir = tmp_path / "database"
    database = database_dir / "kamera.sqlite3"
    registry = database_dir / "bibliothekar-global.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereiche" / "Kamerabibliothek"
    archive = tmp_path / "archive"

    database_dir.mkdir()
    workspace.mkdir()
    archive.mkdir()
    initialize_database(database)
    initialize_library_registry(registry)
    ensure_workspace_layout(workspace, create_default_main=False)

    monkeypatch.setattr(main, "DATABASE_DIRECTORY", database_dir)
    monkeypatch.setattr(main, "DATABASE_FILE", database)
    monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
    monkeypatch.setattr(main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(main, "MAIN_LIBRARY_CONTEXT", main.build_main_library_context())
    monkeypatch.setattr(
        main,
        "inspect_library_paths",
        lambda *args, **kwargs: {
            "valid": True,
            "work_root": str(work),
            "archive_root": str(archive),
            "managed_default_work_root": True,
            "archive_read_only": True,
            "hardlink_to_central_stock": True,
            "errors": [],
            "warnings": [],
        },
    )

    result = main.api_create_library(
        {
            "display_name": "Kamerabibliothek",
            "work_root": "",
            "archive_root": str(archive),
        }
    )

    stored = get_library(registry, MAIN_LIBRARY_ID, active_only=False)
    assert stored is not None
    assert result["library"]["display_name"] == "Kamerabibliothek"
    assert str(stored["display_name"]) == "Kamerabibliothek"
    assert bool(stored["is_main"]) is True
    assert Path(str(stored["database_path"])) == database.resolve()
    assert Path(str(stored["work_root"])) == work.resolve()
    assert work.is_dir()
    assert not (workspace / "Arbeitsbereiche" / "main").exists()


def test_0329_physical_xmp_exports_are_visible_in_day_plan_and_event(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_layout(workspace, create_default_main=False)
    initialize_database(database)

    job_id, family_ids = _seed_19_file_free_day(database, workspace)

    overview = list_job_planning_overview(
        database,
        job_id,
        workspace_path=workspace,
    )
    day = next(
        group
        for group in overview["available_day_groups"]
        if group.get("day_key") == "2026-07-19"
    )
    assert day["family_count"] == 8
    assert day["file_count"] == 19

    summary = build_global_workspace_summary(
        database,
        [job_id],
        workspace_path=workspace,
    )
    assert summary["statistics"]["file_count"] == 19

    event_id = _planned_event(database, job_id, family_ids)
    context = get_event_edit_context(
        database,
        job_id,
        event_id,
        workspace_path=workspace,
    )
    assigned = [
        row for row in context["families"]
        if row.get("assigned_here")
    ]
    assert len(assigned) == 8
    assert sum(int(row["file_count"]) for row in assigned) == 19
    kinds = {
        kind
        for row in assigned
        for kind in (row.get("workspace_asset_kinds") or [])
    }
    assert {"xmp", "export"} <= kinds


def test_0329_sort_plan_uses_configured_work_root_and_all_19_physical_files(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereiche" / "Arbeitsbereich"
    archive = tmp_path / "archive"
    workspace.mkdir()
    work.mkdir(parents=True)
    archive.mkdir()
    ensure_workspace_layout(
        workspace,
        configured_main_work_root=work,
    )
    initialize_database(database)

    job_id, family_ids = _seed_19_file_free_day(database, workspace)
    event_id = _planned_event(database, job_id, family_ids)

    context = LibraryContext(
        library_id=MAIN_LIBRARY_ID,
        display_name="Kamerabibliothek",
        database_path=database,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=True,
        settings={},
    )
    compatibility_root = main.compatibility_workspace_root(context)

    assert not (workspace / "Arbeitsbereiche" / "main").exists()

    plan = build_event_sort_plan(
        database,
        job_id,
        event_id,
        compatibility_root,
        verify_sha256=True,
    )

    assert Path(plan["target_root"]).resolve() == work.resolve()
    assert plan["summary"]["camera_file_count"] == 16
    assert plan["summary"]["asset_count"] == 3
    assert plan["summary"]["file_count"] == 19
    assert plan["summary"]["blocker_count"] == 0, plan["blockers"]
    assert plan["summary"]["ready"] is True
    assert {str(asset["asset_kind"]) for asset in plan["assets"]} == {
        "xmp",
        "export",
    }
