"""Regression tests for 0.54.1 startup provenance, translations, and mobile layout."""
from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from app import main
from app.global_library_inventory import backfill_library_inventory
from app.library_registry import (
    MAIN_LIBRARY_ID, LibraryRegistryError, get_source_backup,
    initialize_library_registry, register_source_backup,
)
from app.events_ui import EVENTS_HTML


def _backfill_fixture(monkeypatch, source_path="/workspace/.trash-import/TRASH_IMPORT_1"):
    import app.global_library_inventory as inventory
    digest = hashlib.sha256(b"validated-camera-file").hexdigest()
    source_signature = "e" * 64
    rows = [{
        "job_id": "TRASH_IMPORT_1", "family_key": "photo",
        "source_signature": source_signature, "source_fingerprint": "f" * 64,
        "source_device_id": None, "source_path": source_path,
        "original_relative_path": "photo.jpg",
        "sha256_original": digest, "size_bytes": len(b"validated-camera-file"),
        "media_type": "jpeg",
    }]
    monkeypatch.setattr(inventory, "_database_family_rows", lambda db: rows)
    return source_signature


def _registry(tmp_path, old_identity, old_path, metadata=None, kind="import"):
    path = tmp_path / "registry.sqlite3"
    initialize_library_registry(path)
    register_source_backup(
        path, backup_id="main:TRASH_IMPORT_1", source_kind=kind,
        source_identity=old_identity, backup_path=old_path,
        metadata=metadata if metadata is not None else {
            "library_id": MAIN_LIBRARY_ID, "job_id": "TRASH_IMPORT_1",
        },
    )
    return path


def test_0541_recovers_only_stale_job_snapshot_source_identity(tmp_path, monkeypatch):
    source_path = "/workspace/.trash-import/TRASH_IMPORT_1"
    signature = _backfill_fixture(monkeypatch, source_path)
    registry = _registry(tmp_path, source_path, source_path)
    from app.database import initialize_database, create_job
    initialize_database(tmp_path / "unused.sqlite3")
    create_job(tmp_path / "unused.sqlite3",job_id="TRASH_IMPORT_1",kind="sd_import",trigger_type="manual",source_path=source_path,working_path="/workspace")
    from app.database import database_connection
    with database_connection(tmp_path / "unused.sqlite3") as c:
        c.execute("UPDATE jobs SET source_signature=? WHERE id='TRASH_IMPORT_1'",(signature,))
    backfill_library_inventory(
        registry, database_path=tmp_path / "unused.sqlite3",
        library_id=MAIN_LIBRARY_ID, claim_all_owned=False,
    )
    restored = get_source_backup(registry, "main:TRASH_IMPORT_1")
    assert restored["source_identity"] == signature
    assert restored["source_kind"] == "import"
    assert restored["backup_path"] == source_path
    # The reconciliation is idempotent on a following startup.
    backfill_library_inventory(
        registry, database_path=tmp_path / "unused.sqlite3",
        library_id=MAIN_LIBRARY_ID, claim_all_owned=False,
    )
    assert get_source_backup(registry, "main:TRASH_IMPORT_1")["source_identity"] == signature


@pytest.mark.parametrize("change", ["unrelated_identity", "changed_path", "wrong_metadata", "different_kind"])
def test_0541_rejects_foreign_or_unverifiable_backup_bindings(tmp_path, monkeypatch, change):
    source_path = "/workspace/.trash-import/TRASH_IMPORT_1"
    _backfill_fixture(monkeypatch, source_path)
    old_identity = "different-source" if change == "unrelated_identity" else source_path
    old_path = "/another/directory" if change == "changed_path" else source_path
    metadata = (
        {"library_id": MAIN_LIBRARY_ID, "job_id": "ANOTHER_JOB"}
        if change == "wrong_metadata" else None
    )
    old_kind = "existing_library" if change == "different_kind" else "import"
    registry = _registry(tmp_path, old_identity, old_path, metadata, old_kind)
    before = get_source_backup(registry, "main:TRASH_IMPORT_1")
    with pytest.raises(LibraryRegistryError):
        backfill_library_inventory(
            registry, database_path=tmp_path / "unused.sqlite3",
            library_id=MAIN_LIBRARY_ID, claim_all_owned=False,
        )
    after = get_source_backup(registry, "main:TRASH_IMPORT_1")
    assert after["source_identity"] == before["source_identity"]
    assert after["source_kind"] == before["source_kind"]
    assert after["backup_path"] == before["backup_path"]


def test_0541_english_health_error_codes_and_clear_fallback():
    assert main.database_initialization_error_code(
        "Eine bestehende Backup-ID darf nicht auf eine andere Quelle umgebunden werden."
    ) == "backup_source_conflict"
    assert main.database_initialization_error_code(
        "Eine bestehende Backup-ID darf nicht auf einen anderen Quellentyp umgebunden werden."
    ) == "backup_kind_conflict"
    assert main.database_initialization_error_code("unidentified database error") == "database_initialization_error"
    assert main.database_initialization_error_code(None) is None
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "An existing backup ID cannot be reassigned to a different source." in source
    assert "Database initialization failed. Check the server logs." in source
    assert 'database.error_code' in source


def test_0541_event_edit_layout_is_dialog_width_aware_not_only_media_queries():
    assert "container-name:event-editor" in EVENTS_HTML
    assert "@container event-editor (max-width:720px)" in EVENTS_HTML
    assert "#event-edit-dialog .child-segment-boundaries" in EVENTS_HTML
    assert "#event-edit-dialog .edit-field > input" in EVENTS_HTML
    assert "inline-size:100% !important" in EVENTS_HTML
    assert "grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr))" in EVENTS_HTML
