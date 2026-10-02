from __future__ import annotations

from pathlib import Path

from app import main, ui_shell
from app.database import database_connection, initialize_database
from app.library_registry import (
    MAIN_LIBRARY_ID,
    adopt_main_library,
    get_library,
    initialize_library_registry,
    update_library_paths,
)
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
