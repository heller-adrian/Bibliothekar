"""0.27.6: Regressionen aus dem Clean-Slate-Manuallauf."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.archive_reversal import prepare_archive_reversal
from app.database import database_connection, delete_planned_event, list_global_tasks
from app.event_change_apply import (
    cancel_event_change,
    confirm_event_change,
    verify_event_change,
)
from app.event_change_request import get_event_change_files, propose_event_change
from app.event_structure import EventPreviewError, build_event_preview
from app.planning import list_global_released_archive_groups
from app.sort_apply import CONFIRMATION_PHRASE, execute_sort_run, prepare_sort_run
from app.sort_plan import build_event_sort_plan
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from tests.backend.archive_change_helpers import copy_prepared_event_document
from tests.backend.test_0271_archive_assistant import _preview, _seed, NOW
from tests.backend.test_0271_archive_release_stock import _release_case
from tests.backend.test_0275_patch import _finish_release_case

ROOT = Path(__file__).resolve().parents[2]


def _family(fid: int, capture: str) -> dict:
    return {
        "family_id": fid,
        "has_date": True,
        "day_key": capture[:10],
        "selected_capture_time": capture,
        "file_count": 2,
    }


def test_0276_no_event_is_one_month_and_uses_canonical_name():
    families = [
        _family(1, "2026-07-25T10:00:00"),
        _family(2, "2026-09-15T10:00:00"),
    ]
    with pytest.raises(EventPreviewError, match="Kalendermonats"):
        build_event_preview(
            {
                "event_kind": "no_event",
                "no_event_segments": [
                    {"day_key": "2026-07-25", "start_time": "00:00", "end_time": "23:59"},
                    {"day_key": "2026-09-15", "start_time": "00:00", "end_time": "23:59"},
                ],
            },
            families,
        )

    preview = build_event_preview(
        {
            "event_kind": "no_event",
            "no_event_segments": [
                {"day_key": "2026-07-25", "start_time": "00:00", "end_time": "23:59"},
            ],
        },
        families,
    )
    assert preview["event_name"] == "07 - Ohne Ereignis"
    assert preview["parent_folder"] == "07 - Ohne Ereignis"


def test_0276_extra_user_file_is_advisory_and_does_not_block_or_break_reversal(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    extra_rel = f"2026/{folder}/eigene Notiz.pdf"
    extra = archive / extra_rel
    extra.write_bytes(b"private-user-document")

    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, None),
        event_name="Test Archiv 2",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    advisory = next(
        row for row in get_event_change_files(db, cr_id)
        if row.get("old_path") == extra_rel
    )
    assert advisory["action"] == "advisory"

    confirm_event_change(db, cr_id, archive, workspace)
    copy_prepared_event_document(db, workspace, archive, cr_id)
    checked = verify_event_change(db, cr_id, archive, workspace)
    assert checked["complete"] is True
    assert checked["advisory_count"] == 1
    assert checked["file_count"] == checked["verified_file_count"]
    assert extra.is_file()

    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["reversal_required"] is True
    prepared = prepare_archive_reversal(db, archive, workspace, cr_id)
    assert prepared["change_request_id"] == cr_id
    assert extra.is_file()
    assert all(
        "eigene Notiz.pdf" not in str(operation)
        for operation in prepared.get("operations") or []
    )


def test_0276_archive_release_provenance_survives_reuse_and_returns_after_delete(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=False)
    _finish_release_case(case)

    with database_connection(case["db"]) as connection:
        marker = connection.execute(
            """SELECT archive_origin FROM released_free_families
               WHERE job_id='old' AND family_id=?""",
            (case["late_family"],),
        ).fetchone()
        assert marker["archive_origin"] == 1
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision,timeline_model,time_model_version
               ) VALUES ('reuse','old',NULL,'parent','Wiederverwendung',
                         '2026-07-22T20:01:00','2026-07-22T23:59:59',1,
                         '07-22 - Wiederverwendung','planned',?,?,'event',0,1,'continuous',2)""",
            (NOW, NOW),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('reuse',?,NULL,'date_time_range',?)""",
            (case["late_family"], NOW),
        )
        connection.commit()

    # Marker bleibt erhalten, ist aber während der Zuordnung weder freie Karte noch Aufgabe.
    assert not any(
        case["late_family"] in item["family_ids"]
        for item in list_global_released_archive_groups(case["db"])
    )
    assert not any(
        item.get("kind") == "released_archive_families"
        for item in list_global_tasks(case["db"])
    )
    with database_connection(case["db"]) as connection:
        assert connection.execute(
            "SELECT archive_origin FROM released_free_families WHERE family_id=?",
            (case["late_family"],),
        ).fetchone()["archive_origin"] == 1

    plan = build_event_sort_plan(
        case["db"], "old", "reuse", case["workspace"], verify_sha256=True
    )
    assert plan["summary"]["ready"], plan["blockers"]
    run = prepare_sort_run(
        case["db"], "old", "reuse", case["workspace"],
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(case["db"], run["id"], case["workspace"])

    with database_connection(case["db"]) as connection:
        used_path = str(connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (case["late_file"],),
        ).fetchone()["current_relative_path"])
        assert not used_path.startswith("Freigewordene Archivdateien/")
        assert connection.execute(
            "SELECT archive_origin FROM released_free_families WHERE family_id=?",
            (case["late_family"],),
        ).fetchone()["archive_origin"] == 1

    deleted = delete_planned_event(case["db"], "old", "reuse")
    assert deleted["pending_delete"] is True
    back_plan = build_workspace_reconcile_plan(
        case["db"], "old", "reuse", case["workspace"]
    )
    assert back_plan["summary"]["ready"], back_plan["blockers"]
    back_run = prepare_workspace_reconcile_run(
        case["db"], "old", "reuse", case["workspace"],
        expected_plan_token=back_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(case["db"], back_run["id"], case["workspace"])

    with database_connection(case["db"]) as connection:
        returned_path = str(connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (case["late_file"],),
        ).fetchone()["current_relative_path"])
        assert returned_path.startswith("Freigewordene Archivdateien/2026/")
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='reuse'"
        ).fetchone()[0] == 0
    assert (case["work"] / returned_path).is_file()
    group = next(
        item for item in list_global_released_archive_groups(case["db"])
        if case["late_family"] in item["family_ids"]
    )
    assert group["start_time"] == "20:01"
    assert group["end_time"] == "23:59"


def test_0276_visible_ui_contracts_and_frozen_disclosures():
    main = (ROOT / "app" / "main.py").read_text()
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    events = (ROOT / "app" / "events_ui.py").read_text()
    assistant = (ROOT / "app" / "archive_change_assistant.py").read_text()

    assert 'trigger === "approved_sd"' in main
    assert '"SD-Kartenimport"' in main
    assert '"Laufwerksimport"' in main
    assert '"Ordnerimport"' in main
    assert "body[data-bk-area=\"archive\"] .archive-verify-button" in shell
    assert "background: var(--bk-yellow) !important" in shell
    assert "vorhandene event.json im Ereignisordner durch die" in assistant
    assert "keine zweite event.json daneben behalten" in assistant

    # Bereits manuell als PASS bestätigt: zentrale Disclosure-Regel unverändert.
    assert "#change-request-dialog details > summary::before" in events
    assert 'font-size:19px' in events
    assert events.count("#change-request-dialog details > summary::before") == 1


def test_0276_workspace_staging_cleanup_prunes_only_empty_descendants():
    source = (ROOT / "app" / "archive_staging.py").read_text()
    assert 'staging_base.rglob("*")' in source
    assert "directory.rmdir()" in source
    assert 'staging_base.mkdir(parents=True, exist_ok=True)' in source
