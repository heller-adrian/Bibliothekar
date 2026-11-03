"""Pre.7.1: no repeated copy, no progress rewind, narrow recovery proofs.

All fixtures live in pytest-managed temporary roots. No TrueNAS mounts,
user cameras, or installed application data are ever used.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.archive_change_assistant import build_archive_change_assistant
from app.archive_release_copy import create_archive_release_copies
from app.archive_release_copy_recovery import recover_archive_release_copy
from app.archive_release_stock import (
    describe_archive_release_stock,
    verify_archive_release_copies,
    verify_archive_release_removal,
)
from app.database import database_connection
from app.event_change_apply import confirm_event_change
from tests.backend.test_0271_archive_release_stock import _release_case, _copy_release_rows


def _prepared_case(tmp_path):
    case = _release_case(tmp_path, with_asset=True)
    confirm_event_change(case["db"], case["cr_id"], case["archive"], case["workspace"])
    return case


def _legacy_regressed_case(tmp_path):
    case=_prepared_case(tmp_path)
    rows=_copy_release_rows(case)
    assert verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    with database_connection(case["db"]) as connection:
        for table in ("event_change_file_reviews","event_change_asset_reviews"):
            connection.execute(
                f"""UPDATE {table}
                    SET verification_status='archive_source_still_exists',
                        verified_at=NULL
                    WHERE change_request_id=?
                      AND verification_status='release_copy_verified'""",
                (case["cr_id"],),
            )
    return case,rows


def test_pre71_early_archive_removal_check_must_not_rewind_verified_copies(tmp_path):
    case=_prepared_case(tmp_path)
    rows=_copy_release_rows(case)
    verified=verify_archive_release_copies(
        case["db"],case["archive"],case["workspace"],case["cr_id"]
    )
    assert verified["complete"]
    status=describe_archive_release_stock(case["db"],case["cr_id"])
    assert status["stage"]=="remove_archive"

    # Premature verify from previous wizard implementation.
    premature=verify_archive_release_removal(
        case["db"],case["archive"],case["workspace"],case["cr_id"]
    )
    assert not premature["complete"]
    assert all(row["status"]=="archive_source_still_exists" for row in premature["files"])
    # The UI may report "still exists", but persistence MUST retain proof.
    again=describe_archive_release_stock(case["db"],case["cr_id"])
    assert again["stage"]=="remove_archive"
    assert again["copy_verified"] is True
    for row in rows:
        assert (case["central"]/row["workspace_release_path"]).is_file()


def test_pre71_occupied_return_path_is_a_safe_nonterminal_result(tmp_path):
    case=_prepared_case(tmp_path)
    rows=_copy_release_rows(case)
    before={
        row["workspace_release_path"]:(
            case["central"]/row["workspace_release_path"]
        ).read_bytes()
        for row in rows
    }
    result=create_archive_release_copies(
        case["db"],case["archive"],case["workspace"],case["cr_id"]
    )
    assert result["complete"] is False
    assert result["error_code"]=="archive_release_target_exists"
    assert {
        rel:(case["central"]/rel).read_bytes() for rel in before
    }==before
    from app import operation_health
    status=operation_health.inspect(case["workspace"])
    assert not [x for x in status["reservations"] if not x["live"]]


def test_pre71_legacy_recovery_restores_only_sha_proven_copy_state(tmp_path,monkeypatch):
    import app.archive_release_copy_recovery as rec
    monkeypatch.setattr(rec,"validate_active_roots",lambda:None)
    case,rows=_legacy_regressed_case(tmp_path)
    archive_before={
        row["old_path"]:hashlib.sha256((case["archive"]/row["old_path"]).read_bytes()).hexdigest()
        for row in rows
    }
    ssd_before={
        row["workspace_release_path"]:hashlib.sha256(
            (case["central"]/row["workspace_release_path"]).read_bytes()
        ).hexdigest()
        for row in rows
    }
    result=recover_archive_release_copy(
        case["db"],case["archive"],case["workspace"],case["cr_id"]
    )
    assert result["recovered"] and not result["archive_modified"]
    assert describe_archive_release_stock(case["db"],case["cr_id"])["stage"]=="remove_archive"
    assert {
        row["old_path"]:hashlib.sha256((case["archive"]/row["old_path"]).read_bytes()).hexdigest()
        for row in rows
    }==archive_before
    assert {
        row["workspace_release_path"]:hashlib.sha256(
            (case["central"]/row["workspace_release_path"]).read_bytes()
        ).hexdigest()
        for row in rows
    }==ssd_before


@pytest.mark.parametrize("damage",["changed_ssd","missing_ssd","changed_original","row_sha","wrong_status"])
def test_pre71_recovery_rejects_unproven_bytes_and_leaves_database_unchanged(
    tmp_path,monkeypatch,damage,
):
    import app.archive_release_copy_recovery as rec
    monkeypatch.setattr(rec,"validate_active_roots",lambda:None)
    case,rows=_legacy_regressed_case(tmp_path)
    row=rows[0]
    if damage=="changed_ssd":
        (case["central"]/row["workspace_release_path"]).write_bytes(b"tamper")
    elif damage=="missing_ssd":
        (case["central"]/row["workspace_release_path"]).unlink()
    elif damage=="changed_original":
        (case["archive"]/row["old_path"]).write_bytes(b"tamper")
    else:
        with database_connection(case["db"]) as connection:
            if damage=="row_sha":
                connection.execute(
                    "UPDATE event_change_file_reviews SET actual_sha256=? WHERE id=?",
                    ("0"*64,row["id"]),
                )
            elif damage=="wrong_status":
                connection.execute(
                    "UPDATE event_change_file_reviews SET verification_status='pending' WHERE id=?",
                    (row["id"],),
                )
    with pytest.raises(ValueError,match="archive_release_recovery_"):
        recover_archive_release_copy(
            case["db"],case["archive"],case["workspace"],case["cr_id"]
        )
    assert describe_archive_release_stock(case["db"],case["cr_id"])["stage"]=="copy_to_ssd"


def test_pre71_ui_gates_step3_without_confirmed_work_and_retains_undo_tabs():
    from app.events_ui import EVENTS_HTML
    from app.ui_shell import BIBLIOTHEKAR_JS
    assert "bk-pre71-manual-confirmed:" in EVENTS_HTML
    assert 'live.release_stock?.stage!=="complete"' in EVENTS_HTML
    assert 'data-reversal-step="' in EVENTS_HTML
    assert "bk-external-rename-close" in BIBLIOTHEKAR_JS
    assert "manual folder/file change detected" in BIBLIOTHEKAR_JS
