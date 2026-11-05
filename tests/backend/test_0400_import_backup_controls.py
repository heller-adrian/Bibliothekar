"""0.40.0: Importabbruch, Sicherungslöschung und Speicherhinweis."""
from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

pytestmark = pytest.mark.usefixtures('isolated_registered_metadata_config')

from app import main
from app.backup_management import backup_deletion_status, delete_backup
from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    get_job,
    initialize_database,
)
from app.folder_import import ImportCancelled, run_folder_import_job
from app.library_registry import adopt_main_library, initialize_library_registry
from app.workspace_layout import backup_root, ensure_workspace_layout


NOW = "2026-10-04T12:00:00+00:00"


def _foundation(tmp_path: Path):
    database = tmp_path / "database" / "kamera.sqlite3"
    registry = tmp_path / "database" / "bibliothekar-global.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    layout = ensure_workspace_layout(workspace)
    initialize_database(database)
    # Establish the same F14 state that a real installation retains before
    # registration; do not bootstrap it after registration as if it were lost.
    from unittest.mock import patch
    import os
    from app.root_operations import reserve
    from app.storage_config import storage_paths
    with patch.dict(os.environ,{"KAMERA_REGISTRY_DATABASE":str(registry)}):
        with reserve(workspace,library_id="main",database=database,kind="startup",
                     ids={"function":"tests.backend.test_0400_import_backup_controls._foundation"},
                     paths=[workspace,Path(layout["work_root"]),archive,*storage_paths(workspace).values()]):
            pass
    initialize_library_registry(registry)
    adopt_main_library(
        registry,
        database_path=database,
        workspace_root=workspace,
        work_root=Path(layout["work_root"]),
        archive_root=archive,
    )
    return database, registry, workspace


def _completed_backup(
    database: Path,
    workspace: Path,
    *,
    job_id: str = "IMPORT_0400",
):
    create_job(
        database,
        job_id=job_id,
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
        source_path="/source",
        source_volume_label="Testquelle",
    )
    payload = b"bibliothekar-0.40.0-backup"
    digest = hashlib.sha256(payload).hexdigest()
    relative = Path("2026") / "2026-10-04" / "20261004_120000_Test.JPG"
    target = backup_root(workspace) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)

    with database_connection(database) as connection:
        family_id = int(
            connection.execute(
                """
                INSERT INTO file_families(
                    job_id,family_key,original_stem,status,
                    selected_capture_time,capture_time_confidence
                )
                VALUES (?, 'family-0400', 'IMG_0400', 'complete',
                        '2026-10-04T12:00:00', 'high')
                """,
                (job_id,),
            ).lastrowid
        )
        connection.execute(
            """
            INSERT INTO files(
                job_id,family_id,original_relative_path,current_relative_path,
                original_filename,extension,media_type,size_bytes,
                sha256_original,sha256_current,selected_capture_time,
                selected_capture_source,capture_time_confidence,review_status,
                metadata_write_status,current_root_kind,created_at,updated_at
            )
            VALUES (?, ?, 'DCIM/IMG_0400.JPG', ?, 'IMG_0400.JPG', '.JPG',
                    'jpeg', ?, ?, ?, '2026-10-04T12:00:00', 'qa', 'high',
                    'not_required', 'not_requested', 'shared_workspace',
                    ?, ?)
            """,
            (
                job_id,
                family_id,
                relative.as_posix(),
                len(payload),
                digest,
                digest,
                NOW,
                NOW,
            ),
        )
        connection.execute(
            """
            UPDATE jobs
            SET state='completed', stage='organized_verified',
                progress_message='Abgeschlossen',
                finished_at=?, updated_at=?
            WHERE id=?
            """,
            (NOW, NOW, job_id),
        )
    return target, family_id


def _planned_preview(family_id: int) -> dict:
    return {
        "event_kind": "event",
        "event_name": "Test",
        "start_date": "2026-10-04",
        "end_date": "2026-10-04",
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "parent_folder": "10-04 - Test",
        "child_folder": None,
        "child_event_name": None,
        "selected_family_ids": [family_id],
        "structure_lines": [],
    }


def test_0400_import_ui_explains_copy_and_exposes_controls():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "Sicherungen werden als Kopie angelegt" in source
    assert "zusätzlichen Speicherplatz" in source
    assert 'data-cancel-import=' in source
    assert 'data-delete-backup=' in source
    assert "window.BibliothekarI18n.confirmAsync(" in source
    assert "/cancel" in source
    assert "/api/backups/" in source


def test_0400_folder_import_cancel_retains_protocol_and_source(tmp_path: Path):
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    logs = tmp_path / "logs"
    source.mkdir()
    workspace.mkdir()
    logs.mkdir()
    (source / "IMG_0001.JPG").write_bytes(b"camera")

    with pytest.raises(ImportCancelled):
        run_folder_import_job(
            source=source,
            workspace=workspace,
            pool_probe_path=workspace,
            log_dir=logs,
            processing_buffer_percent=0,
            safety_reserve_gib=0,
            job_id="CANCEL_0400",
            central_stock=True,
            cancellation_callback=lambda: True,
        )

    assert (source/"IMG_0001.JPG").read_bytes()==b"camera"
    assert (backup_root(workspace)/".incoming"/"CANCEL_0400").exists()


def test_0400_completed_unused_backup_can_be_deleted(tmp_path: Path):
    database, registry, workspace = _foundation(tmp_path)
    target, _ = _completed_backup(database, workspace)

    status = backup_deletion_status(
        database,
        registry,
        backup_root(workspace),
        "IMPORT_0400",
    )
    assert status["allowed"] is True

    result = delete_backup(
        database,
        registry,
        backup_root(workspace),
        "IMPORT_0400",
    )
    assert result["deleted_file_count"] == 1
    assert not target.exists()
    assert get_job(database, "IMPORT_0400") is None


def test_0400_backup_delete_is_blocked_after_event_exists(tmp_path: Path):
    database, registry, workspace = _foundation(tmp_path)
    target, family_id = _completed_backup(database, workspace)

    create_planned_event(
        database,
        "IMPORT_0400",
        _planned_preview(family_id),
    )

    status = backup_deletion_status(
        database,
        registry,
        backup_root(workspace),
        "IMPORT_0400",
    )
    assert status["allowed"] is False
    assert "Ereignis" in status["reason"]
    assert target.exists()
