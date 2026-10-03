from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

from app import main, source_helper, ui_shell
from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    initialize_database,
)
from app.global_library_inventory import (
    backfill_library_claims,
    backfill_library_inventory,
    occurrence_key,
)
from app.library_context import LibraryContext
from app.library_registry import (
    MAIN_LIBRARY_ID,
    adopt_main_library,
    ensure_library_identity,
    get_library,
    get_source_family_claim,
    initialize_library_registry,
    list_libraries,
    list_source_family_members,
    register_library,
    register_source_backup,
    register_source_family,
    register_source_family_members,
    register_source_media,
    set_library_active,
    unregister_library,
    update_library_display_name,
)
from app.library_runtime import (
    get_current_library,
    reset_current_library,
    set_current_library,
)
from app.planning import list_job_available_families
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-01T12:00:00+00:00"


def _insert_family(
    database_path: Path,
    *,
    job_id: str,
    family_key: str,
    capture_time: str,
    sha256: str,
) -> int:
    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO file_families(
                job_id,
                family_key,
                original_stem,
                status,
                selected_capture_time,
                capture_time_confidence
            )
            VALUES (?, ?, ?, 'complete', ?, 'high')
            """,
            (job_id, family_key, family_key, capture_time),
        )
        family_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO files(
                job_id,
                family_id,
                original_relative_path,
                current_relative_path,
                original_filename,
                extension,
                media_type,
                size_bytes,
                sha256_original,
                sha256_current,
                selected_capture_time,
                selected_capture_source,
                capture_time_confidence,
                review_status,
                metadata_write_status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, '.JPG', 'jpeg', 1234, ?, ?, ?, 'qa', 'high',
                    'not_required', 'not_requested', ?, ?)
            """,
            (
                job_id,
                family_id,
                f"DCIM/{family_key}.JPG",
                f"2026/2026-10-01/{family_key}.JPG",
                f"{family_key}.JPG",
                sha256,
                sha256,
                capture_time,
                NOW,
                NOW,
            ),
        )
    return family_id


def _event_preview(
    *,
    family_id: int,
    name: str,
    day: str,
) -> dict:
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


def _main_foundation(tmp_path: Path):
    database = tmp_path / "database" / "kamera.sqlite3"
    registry = tmp_path / "database" / "bibliothekar-global.sqlite3"
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
    return database, registry, workspace, archive


def test_0310_versions_and_frozen_css_contract():
    assert main.DEPLOYMENT_VERSION == "0.32.10"
    assert source_helper.app.version == "0.32.10"
    assert source_helper.healthz()["version"] == "0.32.10"
    assert len(ui_shell.BIBLIOTHEKAR_CSS) == 43515
    assert ".bk-library-card" not in ui_shell.BIBLIOTHEKAR_CSS
    assert ".bk-library-card" in ui_shell.BIBLIOTHEKAR_0310_CSS


def test_0310_registry_v2_tracks_media_and_family_members(tmp_path):
    registry = tmp_path / "registry.sqlite3"
    status = initialize_library_registry(registry)
    assert status["schema_versions"] == [1, 2, 3]

    register_source_backup(
        registry,
        backup_id="backup-1",
        source_kind="sd_backup",
        source_identity="sd-001",
        backup_path="/workspace/SD-Kartensicherungen/SD01",
    )
    family = register_source_family(
        registry,
        source_family_key="backup-1:family-1",
        backup_id="backup-1",
        family_key="family-1",
        content_fingerprint="family-members-sha256:test-0310",
    )
    media = register_source_media(
        registry,
        backup_id="backup-1",
        relative_path="DCIM/100TEST/IMG_0001.JPG",
        size_bytes=1234,
        sha256="a" * 64,
        media_type="jpeg",
    )
    assert register_source_family_members(
        registry,
        source_family_key="backup-1:family-1",
        media_ids=[str(media["media_id"])],
    ) == 1

    members = list_source_family_members(
        registry,
        "backup-1:family-1",
    )
    assert family["canonical_family_id"]
    assert [row["relative_path"] for row in members] == [
        "DCIM/100TEST/IMG_0001.JPG"
    ]
    assert members[0]["sha256"] == "a" * 64


def test_0310_startup_backfill_claims_only_assigned_families(tmp_path):
    database, registry, workspace, archive = _main_foundation(tmp_path)
    create_job(
        database,
        job_id="JOB_0310",
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
        source_path="/source",
        source_signature="source-0310",
    )

    planned_family = _insert_family(
        database,
        job_id="JOB_0310",
        family_key="planned",
        capture_time="2026-10-01T10:00:00",
        sha256="1" * 64,
    )
    applied_family = _insert_family(
        database,
        job_id="JOB_0310",
        family_key="applied",
        capture_time="2026-10-02T10:00:00",
        sha256="2" * 64,
    )
    _insert_family(
        database,
        job_id="JOB_0310",
        family_key="free",
        capture_time="2026-10-03T10:00:00",
        sha256="3" * 64,
    )

    planned = create_planned_event(
        database,
        "JOB_0310",
        _event_preview(
            family_id=planned_family,
            name="Geplant",
            day="2026-10-01",
        ),
    )
    applied = create_planned_event(
        database,
        "JOB_0310",
        _event_preview(
            family_id=applied_family,
            name="Angewendet",
            day="2026-10-02",
        ),
    )
    applied_event_id = str(applied["parent_event"]["id"])
    with database_connection(database) as connection:
        connection.execute(
            """
            UPDATE events
            SET status='applied', applied_at=?, updated_at=?
            WHERE id=?
            """,
            (NOW, NOW, applied_event_id),
        )

    inventory = backfill_library_inventory(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )
    claims = backfill_library_claims(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
    )

    assert inventory["family_count"] == 3
    assert claims == {
        "reserved_count": 1,
        "owned_count": 1,
        "claim_count": 2,
    }

    planned_claim = get_source_family_claim(
        registry,
        occurrence_key(MAIN_LIBRARY_ID, "JOB_0310", "planned"),
    )
    applied_claim = get_source_family_claim(
        registry,
        occurrence_key(MAIN_LIBRARY_ID, "JOB_0310", "applied"),
    )
    free_claim = get_source_family_claim(
        registry,
        occurrence_key(MAIN_LIBRARY_ID, "JOB_0310", "free"),
    )

    assert planned_claim["claim_state"] == "reserved"
    assert planned_claim["event_id"] == str(planned["parent_event"]["id"])
    assert applied_claim["claim_state"] == "owned"
    assert applied_claim["event_id"] == applied_event_id
    assert free_claim is None


def test_0310_planning_projection_can_hide_globally_blocked_family_ids(tmp_path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    create_job(
        database,
        job_id="JOB_FILTER",
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
    )
    first = _insert_family(
        database,
        job_id="JOB_FILTER",
        family_key="first",
        capture_time="2026-10-01T10:00:00",
        sha256="4" * 64,
    )
    second = _insert_family(
        database,
        job_id="JOB_FILTER",
        family_key="second",
        capture_time="2026-10-01T11:00:00",
        sha256="5" * 64,
    )

    visible = list_job_available_families(
        database,
        "JOB_FILTER",
        excluded_family_ids={first},
    )
    assert [int(row["family_id"]) for row in visible] == [second]


def test_0310_library_runtime_context_is_task_local(tmp_path):
    first = LibraryContext(
        library_id="first",
        display_name="First",
        database_path=tmp_path / "first.sqlite3",
        workspace_root=tmp_path / "workspace",
        work_root=tmp_path / "first-work",
        archive_root=tmp_path / "first-archive",
        is_main=False,
        settings={},
    )
    second = LibraryContext(
        library_id="second",
        display_name="Second",
        database_path=tmp_path / "second.sqlite3",
        workspace_root=tmp_path / "workspace",
        work_root=tmp_path / "second-work",
        archive_root=tmp_path / "second-archive",
        is_main=False,
        settings={},
    )

    async def read_after_yield(context: LibraryContext) -> str:
        token = set_current_library(context)
        try:
            await asyncio.sleep(0)
            current = get_current_library()
            assert current is not None
            return current.library_id
        finally:
            reset_current_library(token)

    async def run_both():
        return await asyncio.gather(
            read_after_yield(first),
            read_after_yield(second),
        )

    assert asyncio.run(run_both()) == ["first", "second"]
    assert get_current_library() is None


def test_0310_library_management_is_nondestructive_registry_state(tmp_path):
    main_db, registry, workspace, archive = _main_foundation(tmp_path)

    business_db = tmp_path / "database" / "business.sqlite3"
    business_work = tmp_path / "business-work"
    business_archive = tmp_path / "business-archive"
    business_work.mkdir()
    business_archive.mkdir()
    initialize_database(business_db)
    ensure_library_identity(business_db, "business")

    register_library(
        registry,
        library_id="business",
        display_name="Business",
        database_path=business_db,
        workspace_root=workspace,
        work_root=business_work,
        archive_root=business_archive,
        is_active=True,
    )
    renamed = update_library_display_name(
        registry,
        "business",
        "Business Fotos",
    )
    assert renamed["display_name"] == "Business Fotos"

    assert set_library_active(
        registry,
        "business",
        False,
    )["is_active"] is False
    assert business_db.is_file()
    assert business_archive.is_dir()

    assert set_library_active(
        registry,
        "business",
        True,
    )["is_active"] is True
    unregistered = unregister_library(registry, "business")
    assert unregistered["is_registered"] is False
    assert business_db.is_file()
    assert business_archive.is_dir()
    assert "business" not in {
        row["library_id"]
        for row in list_libraries(
            registry,
            active_only=False,
            registered_only=True,
        )
    }
    stored = get_library(registry, "business", active_only=False)
    assert stored is not None
    assert stored["is_registered"] is False
    assert main_db.is_file()


def test_0310_source_helper_creates_managed_node_when_host_node_is_missing(
    tmp_path,
    monkeypatch,
):
    node_root = tmp_path / "managed-dev"
    missing = tmp_path / "not-present" / "sdz1"
    created = []

    monkeypatch.setattr(source_helper, "DEVICE_NODE_ROOT", node_root)
    monkeypatch.setattr(
        source_helper,
        "_block_device_numbers",
        lambda kernel_name: (8, 65),
    )
    monkeypatch.setattr(
        source_helper,
        "_node_matches_device",
        lambda path, major, minor: Path(path).exists(),
    )

    def fake_mknod(path, mode, device):
        created.append((Path(path), mode, device))
        Path(path).touch()

    monkeypatch.setattr(source_helper.os, "mknod", fake_mknod)

    path, managed = source_helper._ensure_mount_device_node(
        {
            "device_path": str(missing),
            "kernel_name": "sdz1",
        }
    )

    assert managed is True
    assert Path(path) == node_root / "sdz1"
    assert created
    assert stat.S_IFMT(created[0][1]) == stat.S_IFBLK
    assert created[0][2] == os.makedev(8, 65)
