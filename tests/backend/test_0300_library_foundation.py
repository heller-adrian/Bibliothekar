from pathlib import Path

import pytest

from app.database import initialize_database
from app.library_context import (
    list_active_library_contexts,
    resolve_library_context,
)
from app.library_registry import (
    LibraryRegistryError,
    MAIN_LIBRARY_ID,
    adopt_main_library,
    claim_source_family,
    get_source_family_claim,
    initialize_library_registry,
    list_libraries,
    read_library_identity,
    register_library,
    register_source_backup,
    register_source_family,
    release_source_family_reservation,
)


def _foundation(tmp_path: Path):
    database_dir = tmp_path / "database"
    database_file = database_dir / "kamera.sqlite3"
    registry_file = database_dir / "bibliothekar-global.sqlite3"
    workspace = tmp_path / "workspace"
    work_root = workspace / "Arbeitsbereich"
    archive = tmp_path / "archive"

    workspace.mkdir()
    work_root.mkdir()
    archive.mkdir()

    initialized = initialize_database(database_file)
    initialize_library_registry(registry_file)
    adopted = adopt_main_library(
        registry_file,
        database_path=database_file,
        workspace_root=workspace,
        work_root=work_root,
        archive_root=archive,
    )
    return {
        "database_file": database_file,
        "registry_file": registry_file,
        "workspace": workspace,
        "work_root": work_root,
        "archive": archive,
        "initialized": initialized,
        "adopted": adopted,
    }


def test_0300_main_database_is_adopted_in_place(tmp_path):
    state = _foundation(tmp_path)

    assert state["database_file"].name == "kamera.sqlite3"
    assert state["database_file"].is_file()
    assert state["adopted"]["database_path"] == str(
        state["database_file"].resolve()
    )
    assert state["adopted"]["library_id"] == MAIN_LIBRARY_ID
    assert state["adopted"]["is_main"] is True
    assert read_library_identity(state["database_file"]) == MAIN_LIBRARY_ID


def test_0300_library_identity_is_additive_migration_39(tmp_path):
    state = _foundation(tmp_path)

    assert 39 in state["initialized"]["applied_versions"]
    assert "library_identity" in state["initialized"]["tables"]


def test_0300_main_adoption_is_idempotent(tmp_path):
    state = _foundation(tmp_path)

    second = adopt_main_library(
        state["registry_file"],
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=state["work_root"],
        archive_root=state["archive"],
    )
    rows = list_libraries(state["registry_file"])

    assert second["library_id"] == MAIN_LIBRARY_ID
    assert len(rows) == 1
    assert rows[0]["is_main"] is True


def test_0300_library_context_resolves_from_registry_not_process_global(tmp_path):
    state = _foundation(tmp_path)

    context = resolve_library_context(
        state["registry_file"],
        MAIN_LIBRARY_ID,
    )

    assert context.library_id == MAIN_LIBRARY_ID
    assert context.database_path == state["database_file"].resolve()
    assert context.workspace_root == state["workspace"].resolve()
    assert context.work_root == state["work_root"].resolve()
    assert context.archive_root == state["archive"].resolve()


def test_0300_inactive_library_is_not_in_worker_contexts(tmp_path):
    state = _foundation(tmp_path)
    second_db = tmp_path / "database" / "business.sqlite3"
    second_work = state["workspace"] / "Bibliotheken" / "business"
    second_archive = tmp_path / "business-archive"
    second_work.mkdir(parents=True)
    second_archive.mkdir()

    register_library(
        state["registry_file"],
        library_id="business",
        display_name="Business",
        database_path=second_db,
        workspace_root=state["workspace"],
        work_root=second_work,
        archive_root=second_archive,
        is_active=False,
    )

    contexts = list_active_library_contexts(state["registry_file"])
    assert [context.library_id for context in contexts] == [MAIN_LIBRARY_ID]


def test_0300_registry_rejects_archive_nested_in_workspace(tmp_path):
    state = _foundation(tmp_path)
    nested_archive = state["workspace"] / "Archiv"
    nested_archive.mkdir()

    with pytest.raises(LibraryRegistryError):
        register_library(
            state["registry_file"],
            library_id="unsafe",
            display_name="Unsafe",
            database_path=tmp_path / "unsafe.sqlite3",
            workspace_root=state["workspace"],
            work_root=state["work_root"],
            archive_root=nested_archive,
        )


def test_0300_global_reservation_blocks_second_library(tmp_path):
    state = _foundation(tmp_path)
    second_work = state["workspace"] / "Bibliotheken" / "business"
    second_archive = tmp_path / "business-archive"
    second_work.mkdir(parents=True)
    second_archive.mkdir()
    register_library(
        state["registry_file"],
        library_id="business",
        display_name="Business",
        database_path=tmp_path / "database" / "business.sqlite3",
        workspace_root=state["workspace"],
        work_root=second_work,
        archive_root=second_archive,
        is_active=False,
    )

    register_source_backup(
        state["registry_file"],
        backup_id="backup-1",
        source_kind="sd_backup",
        source_identity="sd-001",
        backup_path="/workspace/SD-Kartensicherungen/SD01",
    )
    register_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        backup_id="backup-1",
        family_key="family-1",
    )

    claim_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
        event_id="event-main",
        claim_state="reserved",
    )

    with pytest.raises(LibraryRegistryError):
        claim_source_family(
            state["registry_file"],
            source_family_key="backup-1:family-1",
            library_id="business",
            event_id="event-business",
            claim_state="reserved",
        )


def test_0300_planned_reservation_can_be_released(tmp_path):
    state = _foundation(tmp_path)
    register_source_backup(
        state["registry_file"],
        backup_id="backup-1",
        source_kind="sd_backup",
        source_identity="sd-001",
        backup_path="/workspace/SD-Kartensicherungen/SD01",
    )
    register_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        backup_id="backup-1",
        family_key="family-1",
    )
    claim_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
        event_id="event-main",
        claim_state="reserved",
    )

    assert release_source_family_reservation(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
    ) is True
    assert get_source_family_claim(
        state["registry_file"],
        "backup-1:family-1",
    ) is None


def test_0300_owned_family_is_not_released_by_event_cancellation(tmp_path):
    state = _foundation(tmp_path)
    register_source_backup(
        state["registry_file"],
        backup_id="backup-1",
        source_kind="sd_backup",
        source_identity="sd-001",
        backup_path="/workspace/SD-Kartensicherungen/SD01",
    )
    register_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        backup_id="backup-1",
        family_key="family-1",
    )
    claim_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
        event_id="event-main",
        claim_state="owned",
    )

    with pytest.raises(LibraryRegistryError):
        release_source_family_reservation(
            state["registry_file"],
            source_family_key="backup-1:family-1",
            library_id=MAIN_LIBRARY_ID,
        )


def test_0300_worker_and_ui_are_library_foundation_aware():
    repo_root = Path(__file__).resolve().parents[2]
    main_source = (repo_root / "app" / "main.py").read_text()
    ui_source = (repo_root / "app" / "ui_shell.py").read_text()
    compose = (repo_root / "compose.example.yaml").read_text()

    assert 'DEPLOYMENT_VERSION = "0.30.0"' in main_source
    assert "list_active_library_contexts(" in main_source
    assert "context.database_path" in main_source
    assert "library_context=context" in main_source
    assert '"/api/libraries/current"' in main_source
    assert "deployment_version" in ui_source
    assert "Kern" in ui_source
    assert "ghcr.io/heller-adrian/bibliothekar:patch-0.30.0" in compose
    assert "KAMERA_REGISTRY_DATABASE: /database/bibliothekar-global.sqlite3" in compose
