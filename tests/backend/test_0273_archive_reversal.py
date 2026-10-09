"""0.27.3: Rückänderung, Löschworkflow und persistente Helper-Wurzeln."""
from __future__ import annotations

import shutil
from pathlib import Path

from app.archive_change_assistant import build_archive_change_assistant
from app.archive_release_stock import (
    verify_archive_release_copies,
    verify_archive_release_removal,
)
from app.archive_reversal import (
    finish_archive_reversal,
    prepare_archive_reversal,
    verify_archive_reversal,
)
from app.database import database_connection
from app.event_change_apply import (
    cancel_event_change,
    confirm_event_change,
    finish_event_change,
    verify_event_change,
)
from app.event_change_request import (
    get_event_change_files,
    propose_archived_event_deletion,
    propose_event_change,
)
from tests.backend.test_0271_archive_assistant import _preview, _seed
from tests.backend.test_0271_archive_release_stock import (
    _copy_release_rows,
    _release_case,
)


def _copy_reversal_event_root(workspace: Path, archive: Path, operation: dict) -> None:
    source_text = str(operation["source"])
    target_text = str(operation["target"])
    assert source_text.startswith("Arbeitsbereich/")
    assert target_text.startswith("Kamerabibliothek/")
    work = workspace / "Arbeitsbereich"
    source = work / source_text.removeprefix("Arbeitsbereich/")
    target_parent = archive / target_text.removeprefix("Kamerabibliothek/")
    target_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target_parent / source.name, dirs_exist_ok=True)


def test_0273_cancel_after_archive_removal_becomes_verified_reversal(tmp_path: Path):
    case = _release_case(tmp_path)
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    rows = _copy_release_rows(case)
    assert verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    for row in rows:
        (case["archive"] / row["old_path"]).unlink()
    assert verify_archive_release_removal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]

    cancelled = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert cancelled["status"] == "rueckaenderung_erforderlich"
    assert cancelled["reversal_required"] is True
    assert cancelled["reversal"]["phase"] == "prepare"

    prepared = prepare_archive_reversal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert prepared["phase"] == "finder"
    restore = next(
        item for item in prepared["operations"]
        if item["kind"] == "restore_from_ssd"
    )
    _copy_reversal_event_root(case["workspace"], case["archive"], restore)

    verified = verify_archive_reversal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert verified["complete"] is True, verified["problems"]

    finished = finish_archive_reversal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert finished["status"] == "abgebrochen"
    assert (case["archive"] / rows[0]["old_path"]).is_file()
    assert (case["work"] / "Später zuordnen").is_dir()
    assert (case["central"] / "Freigewordene Archivdateien").is_dir()
    assert not (
        case["work"] / "Später zuordnen" / "Rückänderung" / case["cr_id"]
    ).exists()


def test_0273_reversal_detects_extra_same_root_directory(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    proposed = propose_event_change(
        db,
        "old",
        "archive",
        _preview(folder, old_family, None),
        event_name="Test Archiv 2",
        notes="nur Test",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)

    extra = archive / "2026" / folder / "NEU-NUR-DURCH-AENDERUNG"
    extra.mkdir()
    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["reversal_required"] is True

    prepared = prepare_archive_reversal(db, archive, workspace, cr_id)
    remove = next(
        item for item in prepared["operations"]
        if item["kind"] == "remove_new_directories"
    )
    assert any("NEU-NUR-DURCH-AENDERUNG" in path for path in remove["paths"])

    extra.rmdir()
    assert verify_archive_reversal(db, archive, workspace, cr_id)["complete"]
    assert finish_archive_reversal(db, archive, workspace, cr_id)["status"] == "abgebrochen"


def test_0273_archived_delete_has_only_release_then_remove_old_root(tmp_path: Path):
    db, workspace, archive, folder, _old_family, _new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    event_root = archive / "2026" / folder
    (event_root / "event.json").write_text('{"old":true}\n', encoding="utf-8")

    proposed = propose_archived_event_deletion(db, "old", "archive")
    cr_id = proposed["change_request_id"]
    before = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert before["phase"] == "prepare"
    assert before["preparation"]["missing_directories"] == []
    assert before["target_structure"]["deleted"] is True

    confirm_event_change(db, cr_id, archive, workspace)
    assert not (workspace / "Arbeitsbereich" / "Später zuordnen" / "2026" / folder).exists()

    rows = [
        row for row in get_event_change_files(db, cr_id)
        if str(row.get("workspace_release_path") or "")
    ]
    assert rows
    work = workspace / "Arbeitsbereich"
    central = workspace / "SD-Kartensicherungen"
    for row in rows:
        source = archive / row["old_path"]
        target = central / row["workspace_release_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    assert verify_archive_release_copies(db, archive, workspace, cr_id)["complete"]
    for row in rows:
        (archive / row["old_path"]).unlink()
    assert verify_archive_release_removal(db, archive, workspace, cr_id)["complete"]

    finder = build_archive_change_assistant(
        db, archive, workspace, cr_id, scan_live=True
    )
    assert [item["kind"] for item in finder["operations"]] == [
        "remove_deleted_event_root"
    ]
    assert all(
        item["kind"] not in {"copy_helper_folders", "copy_files", "move_archive_files"}
        for item in finder["operations"]
    )

    shutil.rmtree(event_root)
    verification = verify_event_change(db, cr_id, archive, workspace)
    assert verification["complete"] is True
    result = finish_event_change(db, cr_id, archive, workspace)
    assert result["event_deleted"] is True
    assert (work / "Später zuordnen").is_dir()
    assert (central / "Freigewordene Archivdateien").is_dir()
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='archive'"
        ).fetchone()[0] == 0


def test_0273_stale_helper_child_is_never_reused_as_current_instruction(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    stale = (
        workspace
        / "Arbeitsbereich"
        / "Später zuordnen"
        / "2026"
        / folder
        / "STALE-VOM-ALTEN-AUFTRAG"
    )
    stale.mkdir(parents=True)

    proposed = propose_event_change(
        db,
        "old",
        "archive",
        _preview(folder, old_family, new_family),
        event_name="Test Archiv 2",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    assistant = build_archive_change_assistant(db, archive, workspace, cr_id)

    rendered = repr(assistant["operations"])
    assert "STALE-VOM-ALTEN-AUFTRAG" not in rendered
    assert any(item["kind"] == "copy_files" for item in assistant["operations"])


def test_0326_reversal_uses_library_specific_display_paths(tmp_path: Path):
    case = _release_case(tmp_path)
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    rows = _copy_release_rows(case)
    assert verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    for row in rows:
        (case["archive"] / row["old_path"]).unlink()
    assert verify_archive_release_removal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]

    cancelled = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert cancelled["reversal_required"] is True

    prepared = prepare_archive_reversal(
        case["db"],
        case["archive"],
        case["workspace"],
        case["cr_id"],
        archive_display_root="Testarchiv",
        work_display_root="Testarbeitsbereich",
    )
    assert prepared["path_labels"] == {
        "archive_root": "Testarchiv",
        "work_root": "Testarbeitsbereich",
    }
    assert prepared["original_stock_path"].startswith(
        "Testarbeitsbereich/Später zuordnen/"
    )
    restore = next(
        item for item in prepared["operations"]
        if item["kind"] == "restore_from_ssd"
    )
    assert restore["source"].startswith("Testarbeitsbereich/")
    assert restore["target"].startswith("Testarchiv/")
