from __future__ import annotations

from pathlib import Path
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main
from app.database import (
    claim_next_job,
    create_job,
    database_connection,
    initialize_database,
)
from app.global_library_inventory import (
    backfill_library_inventory,
    register_analysis_inventory,
)
from app.library_registry import (
    MAIN_LIBRARY_ID,
    get_source_backup,
    initialize_library_registry,
    list_library_import_job_ids,
)


NOW = "2026-10-03T19:55:52+02:00"


def _insert_imported_family(database: Path, job_id: str) -> tuple[str, int]:
    payload = b"real-import-family"
    digest = hashlib.sha256(payload).hexdigest()
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,
                   source_volume_label,source_signature,source_path,
                   created_at,updated_at,finished_at
               ) VALUES (
                   ?,'sd_import','manual','completed','organized_verified',
                   'folder_import','Importtest','real-source-signature',
                   '/sources/nas/Importtest',?,?,?
               )""",
            (job_id, NOW, NOW, NOW),
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
                    "20260721_172808_Fuji-X-E5",
                    "2026-07-21T17:28:08+03:00",
                ),
            ).lastrowid
        )
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
                "2026/2026-07-21/photo.JPG",
                "2026/2026-07-21/photo.JPG",
                "photo.JPG",
                ".JPG",
                "jpeg",
                len(payload),
                digest,
                digest,
                "2026-07-21T17:28:08+03:00",
                "EXIF:ExifIFD:DateTimeOriginal",
                NOW,
                NOW,
            ),
        )
        connection.commit()
    return digest, len(payload)


def test_0334_main_import_registry_survives_startup_backfill(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    registry = tmp_path / "bibliothekar-global.sqlite3"
    initialize_database(database)
    initialize_library_registry(registry)

    job_id = "FOLDER_IMPORT_EXISTING"
    digest, size = _insert_imported_family(database, job_id)
    analysis = {
        "files": [{
            "family_key": "FAMILY",
            "relative_path": "2026/2026-07-21/photo.JPG",
            "media_type": "jpeg",
        }]
    }
    register_analysis_inventory(
        registry,
        library_id=MAIN_LIBRARY_ID,
        job_id=job_id,
        source_identity="real-source-signature",
        source_path="/sources/nas/Importtest",
        analysis=analysis,
        checksums={"2026/2026-07-21/photo.JPG": digest},
        sizes={"2026/2026-07-21/photo.JPG": size},
    )

    before = get_source_backup(registry, f"{MAIN_LIBRARY_ID}:{job_id}")
    assert before is not None
    assert before["source_kind"] == "import"

    result = backfill_library_inventory(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )

    assert result["family_count"] == 1
    after = get_source_backup(registry, f"{MAIN_LIBRARY_ID}:{job_id}")
    assert after is not None
    assert after["source_kind"] == "import"
    assert after["source_identity"] == "real-source-signature"
    assert job_id in list_library_import_job_ids(registry, MAIN_LIBRARY_ID)


def test_0334_queued_folder_import_is_claimable_after_backfill(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    registry = tmp_path / "bibliothekar-global.sqlite3"
    initialize_database(database)
    initialize_library_registry(registry)

    _insert_imported_family(database, "OLDER_IMPORT")
    backfill_library_inventory(
        registry,
        database_path=database,
        library_id=MAIN_LIBRARY_ID,
        claim_all_owned=False,
    )

    queued = create_job(
        database,
        job_id="FOLDER_IMPORT_WAITING",
        kind="sd_import",
        trigger_type="manual",
        source_path="/sources/nas/Test",
        working_path="/workspace/SD-Kartensicherungen",
        operation="folder_import",
        source_volume_label="Test",
        source_signature="queued-signature",
    )
    assert queued["state"] == "queued"

    claimed = claim_next_job(database, operation="folder_import")
    assert claimed is not None
    assert claimed["id"] == "FOLDER_IMPORT_WAITING"
    assert claimed["state"] == "copying"
    assert claimed["stage"] == "starting"
    assert claimed["started_at"] is not None


def test_0334_folder_import_rejected_when_startup_is_degraded(monkeypatch):
    monkeypatch.setattr(
        main,
        "DATABASE_INITIALIZATION_ERROR",
        "Eine bestehende Backup-ID darf nicht auf einen anderen Quellentyp umgebunden werden.",
    )
    monkeypatch.setattr(main, "WORKSPACE_LAYOUT_ERROR", None)
    monkeypatch.setattr(main, "LIBRARY_REGISTRY_ERROR", None)

    with pytest.raises(HTTPException) as captured:
        main.api_run_folder_import({})

    assert captured.value.status_code == 503
    assert "Initialisierung fehlgeschlagen" in str(captured.value.detail)


def test_0334_folder_import_rejected_when_initialized_worker_is_dead(monkeypatch):
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr(main, "WORKSPACE_LAYOUT_ERROR", None)
    monkeypatch.setattr(main, "LIBRARY_REGISTRY_ERROR", None)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION", {"ok": True})
    monkeypatch.setattr(main, "WORKSPACE_LAYOUT_INITIALIZATION", {"ok": True})
    monkeypatch.setattr(main, "LIBRARY_REGISTRY_INITIALIZATION", {"ok": True})
    monkeypatch.setattr(main, "WORKER_THREAD", SimpleNamespace(is_alive=lambda: False))

    with pytest.raises(HTTPException) as captured:
        main.api_run_folder_import({})

    assert captured.value.status_code == 503
    assert "Hintergrund-Worker nicht läuft" in str(captured.value.detail)
