"""0.47.7: archive enlargement, irreversible-stop quarantine, SSD background queue."""
from pathlib import Path

import pytest

from app.archive_change_assistant import build_archive_change_assistant
from app.archive_recovery import (
    FORCE_PHRASE, force_stop_reversal, read_recovery_incident,
    resolve_recovery_incident,
)
from app.database import database_connection
from app.event_change_apply import cancel_event_change, confirm_event_change
from app.event_change_request import propose_archived_event_deletion, propose_event_change
from app.ssd_release_background import (
    enqueue_release, claim_release, recover_releases,
    process_release, get_release_task,
)
from tests.backend.test_0271_archive_assistant import _seed, _preview


def test_0476_existing_archive_alle_is_filled_file_by_file(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    req = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = req["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    assistant = build_archive_change_assistant(db, archive, workspace, cr_id)
    operations = assistant["operations"]
    assert [x["kind"] for x in operations] == [
        "copy_files", "replace_event_document"
    ]
    assert operations[0]["file_count"] == 1
    assert operations[0]["items"] == ["neu.JPG"]
    assert operations[0]["target"].endswith("/Alle")
    assert "Alle" not in [
        name for operation in operations
        if operation["kind"] == "copy_helper_folders"
        for name in operation.get("items", [])
    ]
    # No manual operation should ever replace the existing alt.JPG.
    assert (archive / "2026" / folder / "Alle" / "alt.JPG").read_bytes() == b"alt"


def test_0476_forced_reversal_keeps_evidence_and_blocks_edits(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    req = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = req["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    # Operator has partly performed the change but cannot restore it.
    incoming = archive / "2026" / folder / "Alle" / "neu.JPG"
    incoming.write_bytes(b"neu")
    result = cancel_event_change(db, cr_id, archive, workspace)
    assert result["reversal_required"] is True
    with pytest.raises(ValueError, match="NOTFALLABBRUCH"):
        force_stop_reversal(
            db, archive, workspace, cr_id, phrase="wrong",
            reason="Dateien versehentlich gelöscht",
        )
    outcome = force_stop_reversal(
        db, archive, workspace, cr_id, phrase=FORCE_PHRASE,
        reason="Dateien versehentlich gelöscht",
    )
    assert outcome["status"] == "manual_review"
    incident = read_recovery_incident(db, "archive")
    assert incident is not None
    assert incident["snapshot"]["file_evidence"]
    assert incoming.is_file()  # The app never removes archive files.
    with database_connection(db) as connection:
        status = connection.execute(
            "SELECT status FROM event_change_requests WHERE id=?", (cr_id,)
        ).fetchone()["status"]
    assert status == "aenderbar_abgebrochen"
    with pytest.raises(ValueError, match="manuellen Klärung"):
        propose_event_change(
            db, "old", "archive", _preview(folder, old_family, None),
            event_name="Test Archiv 2", archive_root=archive,
            workspace_path=workspace,
        )
    with pytest.raises(ValueError, match="manuellen Klärung"):
        propose_archived_event_deletion(db, "old", "archive", archive_root=archive)
    pending = resolve_recovery_incident(db, archive, workspace, "archive")
    assert not pending["resolved"]
    incoming.unlink()
    restored = resolve_recovery_incident(db, archive, workspace, "archive")
    assert restored["resolved"] is True
    assert read_recovery_incident(db, "archive") is None


def test_0476_release_task_survives_interruption(tmp_path: Path, monkeypatch):
    from app import ssd_release_background as background
    db, workspace, archive, folder, old_family, new_family, _ = _seed(tmp_path)
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE events SET status='applied',archived_at=NULL WHERE id='archive'"
        )
    task = enqueue_release(db, "old", "archive")
    assert task["status"] == "queued"
    assert enqueue_release(db, "old", "archive")["id"] == task["id"]
    claimed = claim_release(db)
    assert claimed["id"] == task["id"]
    assert recover_releases(db) == 1
    claimed = claim_release(db)
    assert claimed["id"] == task["id"]
    assert get_release_task(db, "old", "archive")["status"] == "running"
    monkeypatch.setattr(
        background, "release_event_ssd",
        lambda *args: {"released": True, "deleted_file_count": 1},
    )
    process_release(db, workspace, archive, claimed)
    complete = get_release_task(db, "old", "archive")
    assert complete["status"] == "completed"
    assert complete["progress_percent"] == 100
    assert complete["result"]["deleted_file_count"] == 1
    assert (archive / "2026" / folder / "Alle" / "alt.JPG").exists()


def test_0476_javascript_reversal_has_global_archive_label():
    from app.events_ui import EVENTS_HTML
    from app.transfer_ui import TRANSFER_HTML
    assert EVENTS_HTML.index("const reversalArchiveRoot") < EVENTS_HTML.index('if (phase === "prepare")')
    assert "data-reversal-force" in EVENTS_HTML
    assert "ssd-release/task" in TRANSFER_HTML


def test_0476_missing_original_cannot_be_unlocked_after_forced_stop(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    # Simulate real Finder work before cancelling; otherwise cancellation
    # rightly detects the untouched original and needs no reversal.
    incoming_file = archive / "2026" / folder / "Alle" / "neu.JPG"
    incoming_file.write_bytes(b"neu")
    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["reversal_required"] is True
    lost_original = archive / "2026" / folder / "Alle" / "alt.JPG"
    lost_original.unlink()
    result = force_stop_reversal(
        db, archive, workspace, cr_id, phrase=FORCE_PHRASE,
        reason="Originaldatei wurde außerhalb der App gelöscht",
    )
    assert result["status"] == "manual_review"
    incident = read_recovery_incident(db, "archive")
    assert incident is not None
    assert not incident["snapshot"]["verification"]["complete"]
    assert any(
        p.get("kind") == "file"
        for p in incident["snapshot"]["verification"].get("problems", [])
    )
    unresolved = resolve_recovery_incident(db, archive, workspace, "archive")
    assert unresolved["resolved"] is False
    assert read_recovery_incident(db, "archive") is not None
    assert not lost_original.exists()


def test_0476_failed_release_remains_retriable_and_does_not_touch_archive(
    tmp_path: Path, monkeypatch
):
    from app import ssd_release_background as background
    db, workspace, archive, folder, *_ = _seed(tmp_path)
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE events SET status='applied',archived_at=NULL WHERE id='archive'"
        )
    first = enqueue_release(db, "old", "archive")
    claimed = claim_release(db)
    assert claimed["id"] == first["id"]

    def stop_before_deletion(*args):
        raise RuntimeError("Fehlende Originaldatei / SHA-256 passt nicht")
    monkeypatch.setattr(background, "release_event_ssd", stop_before_deletion)
    process_release(db, workspace, archive, claimed)
    failed = get_release_task(db, "old", "archive")
    assert failed["status"] == "failed"
    assert "SHA-256" in failed["error_message"]
    original = archive / "2026" / folder / "Alle" / "alt.JPG"
    assert original.read_bytes() == b"alt"

    retry = enqueue_release(db, "old", "archive")
    assert retry["id"] != first["id"]
    claimed_retry = claim_release(db)
    monkeypatch.setattr(
        background, "release_event_ssd",
        lambda *args: {"released": True, "deleted_file_count": 1},
    )
    process_release(db, workspace, archive, claimed_retry)
    assert get_release_task(db, "old", "archive")["status"] == "completed"
    assert original.read_bytes() == b"alt"
