"""0.27.2: Archivänderungs-Feinschliff fachlich absichern."""
from pathlib import Path
from app.archive_change_assistant import build_archive_change_assistant
from app.archive_staging import describe_archive_change_staging_for_request, required_event_document_for_request
from app.event_change_apply import confirm_event_change, verify_event_change
from app.event_change_request import propose_event_change
from tests.backend.archive_change_helpers import copy_prepared_event_document
from tests.backend.test_0271_archive_assistant import _preview, _seed

def test_0272_event_document_is_staged_and_required_in_real_workspace_flow(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(tmp_path, full_archive_triplet=True)
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, None),
        event_name="Test Archiv 2", notes="aktualisiert",
        archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    spec = required_event_document_for_request(db, cr_id)
    assert spec is not None
    staged = workspace / "Arbeitsbereich" / "Später zuordnen" / spec["target_relative_path"]
    assert staged.is_file(), [str(path) for path in workspace.rglob("event.json")]
    before = verify_event_change(db, cr_id, archive, workspace)
    assert before["complete"] is False
    assert before["event_document"]["status"] == "missing"
    copy_prepared_event_document(db, workspace, archive, cr_id)
    after = verify_event_change(db, cr_id, archive, workspace)
    assert after["event_document"]["status"] == "verified"
    assert after["complete"] is True

def test_0272_switch_to_day_folders_marks_all_old_direct_branches_obsolete(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(tmp_path, full_archive_triplet=True)
    preview = _preview(folder, old_family, None)
    preview["preserve_day_folders"] = True
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    description = describe_archive_change_staging_for_request(db, archive, proposed["change_request_id"])
    obsolete = set(description["obsolete_directories"])
    assert f"2026/{folder}/Alle" in obsolete
    assert f"2026/{folder}/Sortiert" in obsolete
    assert f"2026/{folder}/Export" in obsolete

def test_0272_live_refresh_recovers_actual_intermediate_source_path(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(tmp_path, full_archive_triplet=True)
    preview = _preview(folder, old_family, None)
    preview["preserve_day_folders"] = True
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    original = archive / "2026" / folder / "Alle" / "alt.JPG"
    intermediate = archive / "2026" / folder / "Sortiert" / "alt.JPG"
    original.replace(intermediate)
    assistant = build_archive_change_assistant(db, archive, workspace, cr_id, scan_live=True)
    moves = [item for item in assistant["operations"] if item["kind"] == "move_archive_files"]
    assert moves
    assert any(
        str(item.get("source") or "").endswith(f"2026/{folder}/Sortiert")
        or any(str(value).endswith(f"2026/{folder}/Sortiert") for value in item.get("sources") or [])
        for item in moves
    )
    assert assistant["live_refreshed"] is True
