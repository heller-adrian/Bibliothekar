"""Pre.6.2: explicit filename review must block concurrent structural changes."""
import json
from app.database import database_connection
from app.external_changes import list_external_change_state
from tests.backend.test_pre61_manual_rename import setup_renamed_file, run_inventory


def test_renamed_file_is_not_silently_accepted_with_event_structure(tmp_path, monkeypatch):
    db, ws, central, work, event, file_id, old, new, old_rel = (
        setup_renamed_file(tmp_path, monkeypatch)
    )
    # A second external operation adds a directory while the JPEG's filename
    # differs from the saved catalogue. Accepting the folder structure must
    # not become an implicit acceptance of the different JPEG filename.
    event_root = old.parent.parent
    (event_root / "Extern hinzugefügt").mkdir()
    archive = tmp_path / "archive"
    archive.mkdir()
    state = run_inventory(db, ws, archive)
    assert any(
        row["kind"] == "filename_rename" and row["file_id"] == file_id
        for row in state["required"]
    ), state
    with database_connection(db) as conn:
        rows = conn.execute(
            "SELECT status,detected_json FROM event_structure_changes "
            "WHERE event_id=? ORDER BY created_at DESC",
            (event["id"],),
        ).fetchall()
        assert rows, "The additional folder must trigger a structural change"
        snapshot = json.loads(rows[0]["detected_json"])
        assert rows[0]["status"] == "blocked"
        assert snapshot["filename_rename_pending_ids"] == [file_id]
        assert conn.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()[0] == old_rel
    # No file has been overwritten or implicitly renamed back.
    assert new.is_file() and not old.exists()
    assert list_external_change_state(db)["required_count"] >= 1
