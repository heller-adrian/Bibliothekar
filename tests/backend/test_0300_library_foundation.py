from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from app import main, source_helper
from app.database import initialize_database
from app.library_context import (
    LibraryContext,
    list_active_library_contexts,
    resolve_library_context,
)
from app.workspace_layout import (
    WorkspaceLayoutError,
    ensure_workspace_layout,
    resolve_library_work_root,
)
from app.library_registry import (
    LibraryRegistryError,
    MAIN_LIBRARY_ID,
    adopt_main_library,
    claim_source_family,
    get_source_family_claim,
    ensure_library_identity,
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

    registry_status = initialize_library_registry(state["registry_file"])
    assert registry_status["schema_versions"] == [1, 2, 3]
    assert registry_status["newly_applied_versions"] == []


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


def test_0300_global_ownership_blocks_duplicate_family_from_second_backup(tmp_path):
    state = _foundation(tmp_path)

    main_root = state["work_root"] / "main"
    business_root = state["work_root"] / "business"
    business_archive = tmp_path / "business-archive"
    business_database = tmp_path / "database" / "business.sqlite3"
    main_root.mkdir()
    business_root.mkdir()
    business_archive.mkdir()

    register_library(
        state["registry_file"],
        library_id=MAIN_LIBRARY_ID,
        display_name="Main Library",
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=main_root,
        archive_root=state["archive"],
        is_main=True,
        is_active=True,
        settings={"adopted_existing_database": True},
    )
    initialize_database(business_database)
    ensure_library_identity(business_database, "business")
    register_library(
        state["registry_file"],
        library_id="business",
        display_name="Business",
        database_path=business_database,
        workspace_root=state["workspace"],
        work_root=business_root,
        archive_root=business_archive,
        is_active=True,
    )

    for backup_id, source_identity in (
        ("backup-1", "sd-001"),
        ("backup-2", "sd-002"),
    ):
        register_source_backup(
            state["registry_file"],
            backup_id=backup_id,
            source_kind="sd_backup",
            source_identity=source_identity,
            backup_path=f"/workspace/SD-Kartensicherungen/{backup_id}",
        )

    first = register_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        backup_id="backup-1",
        family_key="family-1",
        content_fingerprint="family-content-sha256:abc123",
    )
    second = register_source_family(
        state["registry_file"],
        source_family_key="backup-2:family-9",
        backup_id="backup-2",
        family_key="family-9",
        content_fingerprint="family-content-sha256:abc123",
    )
    assert first["canonical_family_id"] == second["canonical_family_id"]

    claim_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
        event_id="event-main",
        claim_state="reserved",
    )
    # Bereits die Planung ist global exklusiv.
    with pytest.raises(
        LibraryRegistryError,
        match="anderen Bibliothek",
    ):
        claim_source_family(
            state["registry_file"],
            source_family_key="backup-2:family-9",
            library_id="business",
            event_id="event-business",
            claim_state="reserved",
        )

    # Apply stuft den bestehenden Claim derselben Bibliothek zu owned hoch.
    claim_source_family(
        state["registry_file"],
        source_family_key="backup-1:family-1",
        library_id=MAIN_LIBRARY_ID,
        event_id="event-main",
        claim_state="owned",
    )
    duplicate_claim = get_source_family_claim(
        state["registry_file"],
        "backup-2:family-9",
    )
    assert duplicate_claim is not None
    assert duplicate_claim["library_id"] == MAIN_LIBRARY_ID
    assert duplicate_claim["claim_state"] == "owned"

    with pytest.raises(
        LibraryRegistryError,
        match="anderen Bibliothek",
    ):
        claim_source_family(
            state["registry_file"],
            source_family_key="backup-2:family-9",
            library_id="business",
            event_id="event-business",
            claim_state="owned",
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
        content_fingerprint="family-content-sha256:release",
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
        content_fingerprint="family-content-sha256:owned",
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

    assert 'DEPLOYMENT_VERSION = "0.54.4"' in main_source
    assert "list_active_library_contexts(" in main_source
    assert "context.database_path" in main_source
    assert "library_context=context" in main_source
    assert '"/api/libraries/current"' in main_source
    assert "deployment_version" in ui_source
    assert "Version <span data-bk-version>0.54.4</span>" in ui_source
    assert "ghcr.io/heller-adrian/bibliothekar:patch-0.54.4" in compose
    assert "KAMERA_REGISTRY_DATABASE: /database/bibliothekar-global.sqlite3" in compose


def test_0300_registry_file_cannot_be_used_as_library_database(tmp_path):
    state = _foundation(tmp_path)

    with pytest.raises(
        LibraryRegistryError,
        match="globale Registry",
    ):
        register_library(
            state["registry_file"],
            library_id="broken",
            display_name="Broken",
            database_path=state["registry_file"],
            workspace_root=state["workspace"],
            work_root=state["work_root"],
            archive_root=state["archive"],
        )


def test_0300_inactive_library_cannot_claim_unowned_family(tmp_path):
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
        backup_id="backup-inactive",
        source_kind="sd_backup",
        source_identity="sd-inactive",
        backup_path="/workspace/SD-Kartensicherungen/SD-inactive",
    )
    register_source_family(
        state["registry_file"],
        source_family_key="backup-inactive:family-1",
        backup_id="backup-inactive",
        family_key="family-1",
        content_fingerprint="family-content-sha256:inactive",
    )

    with pytest.raises(
        LibraryRegistryError,
        match="aktiven Bibliothek",
    ):
        claim_source_family(
            state["registry_file"],
            source_family_key="backup-inactive:family-1",
            library_id="business",
            event_id="event-business",
            claim_state="reserved",
        )


def test_0300_worker_rotates_after_last_served_library(tmp_path):
    state = _foundation(tmp_path)

    main_root = state["work_root"] / "main"
    main_root.mkdir()
    register_library(
        state["registry_file"],
        library_id=MAIN_LIBRARY_ID,
        display_name="Main Library",
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=main_root,
        archive_root=state["archive"],
        is_main=True,
        is_active=True,
        settings={"adopted_existing_database": True},
    )

    for library_id, display_name in (
        ("business", "Business"),
        ("private", "Private"),
    ):
        work_root = state["work_root"] / library_id
        archive_root = tmp_path / f"{library_id}-archive"
        database_path = tmp_path / "database" / f"{library_id}.sqlite3"
        work_root.mkdir(parents=True)
        archive_root.mkdir()
        initialize_database(database_path)
        ensure_library_identity(database_path, library_id)
        register_library(
            state["registry_file"],
            library_id=library_id,
            display_name=display_name,
            database_path=database_path,
            workspace_root=state["workspace"],
            work_root=work_root,
            archive_root=archive_root,
            is_active=True,
        )

    contexts = list_active_library_contexts(state["registry_file"])
    assert [context.library_id for context in contexts] == [
        "main",
        "business",
        "private",
    ]

    rotated = main.ordered_worker_contexts(contexts, "main")
    assert [context.library_id for context in rotated] == [
        "business",
        "private",
        "main",
    ]

    rotated_again = main.ordered_worker_contexts(contexts, "business")
    assert [context.library_id for context in rotated_again] == [
        "private",
        "main",
        "business",
    ]

def test_0300_worker_thumbnail_uses_library_database_and_distinct_cache_key(
    tmp_path,
    monkeypatch,
):
    seen = []
    context = LibraryContext(
        library_id="business",
        display_name="Business",
        database_path=tmp_path / "business.sqlite3",
        workspace_root=tmp_path / "workspace",
        work_root=tmp_path / "workspace" / "Business",
        archive_root=tmp_path / "archive",
        is_main=False,
        settings={},
    )

    def fake_list_job_files(database_path, job_id):
        seen.append((database_path, job_id))
        return []

    monkeypatch.setattr(main, "list_job_files", fake_list_job_files)

    assert main.ensure_job_thumbnail(
        "job-same-id",
        library_context=context,
    ) is None
    assert seen == [(context.database_path, "job-same-id")]
    assert main._thumbnail_path(
        "job-same-id",
        library_id="main",
    ) != main._thumbnail_path(
        "job-same-id",
        library_id="business",
    )


def test_0300_source_helper_requires_exact_mount_target(monkeypatch):
    parent_only = SimpleNamespace(
        returncode=0,
        stdout=json.dumps(
            {
                "filesystems": [
                    {
                        "target": "/sources/removable",
                        "source": "/host/removable",
                        "fstype": "none",
                        "options": "rw",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        source_helper,
        "run",
        lambda *args, **kwargs: parent_only,
    )
    assert source_helper._mount_info(
        "/sources/removable/card-1"
    ) is None

    exact = SimpleNamespace(
        returncode=0,
        stdout=json.dumps(
            {
                "filesystems": [
                    {
                        "target": "/sources/removable/card-1",
                        "source": "/dev/sdz1",
                        "fstype": "vfat",
                        "options": "ro,nosuid,nodev,noexec",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        source_helper,
        "run",
        lambda *args, **kwargs: exact,
    )
    info = source_helper._mount_info(
        "/sources/removable/card-1"
    )
    assert info is not None
    assert info["source"] == "/dev/sdz1"


def test_0300_source_helper_reports_current_deployment_version():
    assert tuple(map(int, source_helper.app.version.split("."))) >= (0, 30, 0)
    assert tuple(map(int, source_helper.healthz()["version"].split("."))) >= (0, 30, 0)


def test_0300_main_adoption_preserves_user_metadata(tmp_path):
    state = _foundation(tmp_path)

    register_library(
        state["registry_file"],
        library_id=MAIN_LIBRARY_ID,
        display_name="Private Fotos",
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=state["work_root"],
        archive_root=state["archive"],
        is_main=True,
        is_active=True,
        settings={
            "custom_setting": "bleibt-erhalten",
            "adopted_existing_database": True,
        },
    )

    migrated_main_root = state["work_root"] / "main"
    migrated_main_root.mkdir()
    register_library(
        state["registry_file"],
        library_id=MAIN_LIBRARY_ID,
        display_name="Private Fotos",
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=migrated_main_root,
        archive_root=state["archive"],
        is_main=True,
        is_active=True,
        settings={
            "custom_setting": "bleibt-erhalten",
            "adopted_existing_database": True,
        },
    )

    adopted_again = adopt_main_library(
        state["registry_file"],
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=state["work_root"],
        archive_root=state["archive"],
    )

    assert adopted_again["display_name"] == "Private Fotos"
    assert adopted_again["settings"]["custom_setting"] == "bleibt-erhalten"
    assert adopted_again["settings"]["adopted_existing_database"] is True
    assert adopted_again["work_root"] == str(migrated_main_root.resolve())


def test_0300_library_work_root_isolated_below_shared_work_area(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_layout(workspace)

    business_root = workspace / "Arbeitsbereich" / "Business"
    resolved = resolve_library_work_root(
        workspace,
        business_root,
    )
    assert resolved == business_root.resolve()
    assert resolved.is_dir()

    unsafe = workspace / "SD-Kartensicherungen" / "Business"
    with pytest.raises(
        WorkspaceLayoutError,
        match="innerhalb",
    ):
        resolve_library_work_root(
            workspace,
            unsafe,
        )


def test_0300_worker_passes_context_work_root_to_both_pipelines():
    repo_root = Path(__file__).resolve().parents[2]
    main_source = (repo_root / "app" / "main.py").read_text()
    folder_source = (repo_root / "app" / "folder_import.py").read_text()
    pipeline_source = (repo_root / "app" / "pipeline.py").read_text()

    assert "work_root=work_root" in main_source
    assert "resolve_library_work_root(" in folder_source
    assert "resolve_library_work_root(" in pipeline_source


def test_0300_active_library_requires_initialized_matching_database(tmp_path):
    state = _foundation(tmp_path)
    work_root = state["workspace"] / "Bibliotheken" / "business"
    archive_root = tmp_path / "business-archive"
    work_root.mkdir(parents=True)
    archive_root.mkdir()

    missing_database = tmp_path / "database" / "missing.sqlite3"
    with pytest.raises(
        LibraryRegistryError,
        match="vorhandene SQLite-Datenbank",
    ):
        register_library(
            state["registry_file"],
            library_id="business",
            display_name="Business",
            database_path=missing_database,
            workspace_root=state["workspace"],
            work_root=work_root,
            archive_root=archive_root,
            is_active=True,
        )

    wrong_database = tmp_path / "database" / "wrong.sqlite3"
    initialize_database(wrong_database)
    ensure_library_identity(wrong_database, "other-library")
    with pytest.raises(
        LibraryRegistryError,
        match="stimmt nicht",
    ):
        register_library(
            state["registry_file"],
            library_id="business",
            display_name="Business",
            database_path=wrong_database,
            workspace_root=state["workspace"],
            work_root=work_root,
            archive_root=archive_root,
            is_active=True,
        )


def test_0300_active_work_roots_must_not_overlap(tmp_path):
    state = _foundation(tmp_path)
    business_database = tmp_path / "database" / "business.sqlite3"
    business_root = state["work_root"] / "business"
    business_archive = tmp_path / "business-archive"
    business_root.mkdir()
    business_archive.mkdir()
    initialize_database(business_database)
    ensure_library_identity(business_database, "business")

    with pytest.raises(
        LibraryRegistryError,
        match="Arbeitsbereiche dürfen sich nicht",
    ):
        register_library(
            state["registry_file"],
            library_id="business",
            display_name="Business",
            database_path=business_database,
            workspace_root=state["workspace"],
            work_root=business_root,
            archive_root=business_archive,
            is_active=True,
        )


def test_0300_active_archive_roots_must_not_overlap(tmp_path):
    state = _foundation(tmp_path)

    migrated_main_root = state["work_root"] / "main"
    migrated_main_root.mkdir()
    register_library(
        state["registry_file"],
        library_id=MAIN_LIBRARY_ID,
        display_name="Main Library",
        database_path=state["database_file"],
        workspace_root=state["workspace"],
        work_root=migrated_main_root,
        archive_root=state["archive"],
        is_main=True,
        is_active=True,
        settings={"adopted_existing_database": True},
    )

    business_database = tmp_path / "database" / "business.sqlite3"
    business_root = state["work_root"] / "business"
    nested_archive = state["archive"] / "business"
    business_root.mkdir()
    nested_archive.mkdir()
    initialize_database(business_database)
    ensure_library_identity(business_database, "business")

    with pytest.raises(
        LibraryRegistryError,
        match="Bibliotheks-Archive dürfen sich nicht",
    ):
        register_library(
            state["registry_file"],
            library_id="business",
            display_name="Business",
            database_path=business_database,
            workspace_root=state["workspace"],
            work_root=business_root,
            archive_root=nested_archive,
            is_active=True,
        )


def test_0300_worker_skips_broken_queue_and_uses_next_library(
    tmp_path,
    monkeypatch,
):
    broken = LibraryContext(
        library_id="broken",
        display_name="Broken",
        database_path=tmp_path / "broken.sqlite3",
        workspace_root=tmp_path / "workspace",
        work_root=tmp_path / "workspace" / "broken",
        archive_root=tmp_path / "archive-broken",
        is_main=False,
        settings={},
    )
    healthy = LibraryContext(
        library_id="healthy",
        display_name="Healthy",
        database_path=tmp_path / "healthy.sqlite3",
        workspace_root=tmp_path / "workspace",
        work_root=tmp_path / "workspace" / "healthy",
        archive_root=tmp_path / "archive-healthy",
        is_main=False,
        settings={},
    )

    healthy.database_path.touch()

    seen = []
    def fake_claim(database_path):
        seen.append(database_path)
        return {"id": "job-healthy"}

    monkeypatch.setattr(main, "claim_next_job", fake_claim)

    claimed = main.claim_next_library_job([broken, healthy])
    assert claimed is not None
    context, job = claimed
    assert context.library_id == "healthy"
    assert job["id"] == "job-healthy"
    assert seen == [healthy.database_path]
    assert broken.database_path.exists() is False


def test_0300_source_family_identity_cannot_be_rebound(tmp_path):
    state = _foundation(tmp_path)
    register_source_backup(
        state["registry_file"],
        backup_id="backup-stable",
        source_kind="sd_backup",
        source_identity="sd-stable",
        backup_path="/workspace/SD-Kartensicherungen/stable",
    )
    register_source_family(
        state["registry_file"],
        source_family_key="backup-stable:family-1",
        backup_id="backup-stable",
        family_key="family-1",
        content_fingerprint="family-content-sha256:stable-a",
    )

    with pytest.raises(
        LibraryRegistryError,
        match="darf nicht",
    ):
        register_source_family(
            state["registry_file"],
            source_family_key="backup-stable:family-1",
            backup_id="backup-stable",
            family_key="family-1",
            content_fingerprint="family-content-sha256:changed",
        )


def test_0300_backup_identity_cannot_be_rebound(tmp_path):
    state = _foundation(tmp_path)
    register_source_backup(
        state["registry_file"],
        backup_id="backup-stable-origin",
        source_kind="sd_backup",
        source_identity="sd-card-a",
        backup_path="/workspace/SD-Kartensicherungen/a",
    )

    with pytest.raises(
        LibraryRegistryError,
        match="andere Quelle",
    ):
        register_source_backup(
            state["registry_file"],
            backup_id="backup-stable-origin",
            source_kind="sd_backup",
            source_identity="sd-card-b",
            backup_path="/workspace/SD-Kartensicherungen/b",
        )
