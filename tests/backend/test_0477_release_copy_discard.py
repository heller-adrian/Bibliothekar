"""0.47.8: refusing to leave orphan SSD copies after discarding archive changes."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.archive_release_stock import ArchiveReleaseStockError, cleanup_archive_release_stock
from app.archive_reversal import finish_archive_reversal, verify_archive_reversal
from app.database import database_connection
from app.event_change_apply import EventChangeApplyError, cancel_event_change, confirm_event_change
from app.event_change_request import get_event_change_files
from tests.backend.test_0271_archive_release_stock import _release_case, _copy_release_rows


def _confirm(case):
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )


def _copies(case):
    rows = _copy_release_rows(case)
    return rows, [case["central"] / row["workspace_release_path"] for row in rows]


def test_0477_discard_removes_verified_copies_and_empty_date_folders(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    _confirm(case)
    rows, copies = _copies(case)
    assert len(rows) == 2
    dirs = {p.parent for p in copies}
    assert all(p.is_file() for p in copies)

    result = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert result["status"] == "abgebrochen"
    assert result["reversal_required"] is False
    assert all(not p.exists() for p in copies)
    assert all(not p.exists() for p in dirs)
    assert (case["central"] / "Freigewordene Archivdateien").is_dir()
    assert all((case["archive"] / row["old_path"]).is_file() for row in rows)


def test_0477_discard_keeps_foreign_files_in_shared_segment(tmp_path: Path):
    case = _release_case(tmp_path)
    _confirm(case)
    rows, copies = _copies(case)
    foreign = copies[0].parent / "Nicht-von-dieser-Aenderung.JPG"
    foreign.write_bytes(b"foreign")
    result = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert result["status"] == "abgebrochen"
    assert not copies[0].exists()
    assert foreign.read_bytes() == b"foreign"
    assert foreign.parent.is_dir()


def test_0477_modified_one_of_two_copies_prevents_partial_cleanup(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    _confirm(case)
    rows, copies = _copies(case)
    assert len(copies) == 2
    copies[-1].write_bytes(b"user-edit")
    with pytest.raises(EventChangeApplyError, match="SSD-Rückkehrkopie wurde verändert"):
        cancel_event_change(
            case["db"], case["cr_id"], case["archive"], case["workspace"]
        )
    # A two-pass safety check prevents deleting the valid first copy.
    assert copies[0].read_bytes() != b"user-edit"
    assert copies[1].read_bytes() == b"user-edit"
    with database_connection(case["db"]) as connection:
        status = connection.execute(
            "SELECT status FROM event_change_requests WHERE id=?",
            (case["cr_id"],),
        ).fetchone()["status"]
    assert status == "aenderbar_bestaetigt"


def test_0477_missing_archive_original_forces_reversal_and_preserves_ssd(tmp_path: Path):
    case = _release_case(tmp_path)
    _confirm(case)
    rows, copies = _copies(case)
    (case["archive"] / rows[0]["old_path"]).unlink()
    result = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert result["reversal_required"] is True
    assert copies[0].is_file()
    # Standalone cleanup must not bypass the original-state prerequisite.
    with pytest.raises(ArchiveReleaseStockError, match="Archivoriginal"):
        cleanup_archive_release_stock(
            case["db"], case["workspace"], case["cr_id"],
            archive_root=case["archive"],
        )
    assert copies[0].is_file()


def test_0477_reversal_cleanup_removes_return_copies_only_after_restoration(tmp_path: Path):
    case = _release_case(tmp_path)
    _confirm(case)
    rows, copies = _copies(case)
    original = case["archive"] / rows[0]["old_path"]
    original.unlink()
    cancelled = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert cancelled["reversal_required"]
    # Even if all that is required is to restore the verified original,
    # the archive must be physically correct before the SSD copy is deleted.
    shutil.copy2(copies[0], original)
    assert verify_archive_reversal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    result = finish_archive_reversal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert result["status"] == "abgebrochen"
    assert original.read_bytes() == case["late_payload"]
    assert not copies[0].exists()
    assert not copies[0].parent.exists()
