"""0.27.0: Archiv-Erweiterungen bleiben kanonisch, auch über Sicherungsaufträge hinweg."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.database import (
    database_connection,
    get_event_edit_context,
    initialize_database,
)
from app.event_change_apply import (
    confirm_event_change,
    finish_event_change,
    verify_event_change,
)
from app.event_change_request import (
    get_event_change_files,
    propose_event_change,
)
from app.planning import list_job_available_families


NOW = "2026-09-28T12:00:00+00:00"


def _seed_job(connection, job_id: str) -> None:
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,source_volume_label,
               created_at,updated_at
           ) VALUES (?, 'sd_import','manual','completed','done','folder_import',?,?,?)""",
        (job_id, job_id.upper(), NOW, NOW),
    )


def _add_family_with_file(
    connection,
    *,
    job_id: str,
    key: str,
    capture: str,
    relative_path: str,
    payload: bytes,
    root_kind: str,
) -> tuple[int, int, str]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, key, key, capture),
        ).lastrowid
    )
    digest = hashlib.sha256(payload).hexdigest()
    file_id = int(
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required',
                         'not_requested',?,?,?)""",
            (
                job_id,
                family_id,
                relative_path,
                relative_path,
                Path(relative_path).name,
                len(payload),
                digest,
                digest,
                capture,
                "DateTimeOriginal",
                NOW,
                NOW,
                root_kind,
            ),
        ).lastrowid
    )
    return family_id, file_id, digest


def _materialize(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _seed_archived_case(tmp_path: Path, *, event_kind: str):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive_root = tmp_path / "archive"
    work_root = workspace / "Arbeitsbereich"
    work_root.mkdir(parents=True)
    archive_root.mkdir()

    initialize_database(db)
    folder = "07.23 - Urlaub" if event_kind == "event" else "07 - Ohne Ereignis"
    old_rel = f"2026/{folder}/Alle/alt.JPG"
    incoming_rel = "2026/Neue-Sicherung/Alle/neu.JPG"
    old_payload = b"archiv-alt"
    incoming_payload = b"ssd-neu"

    with database_connection(db) as connection:
        _seed_job(connection, "old")
        _seed_job(connection, "new")
        old_family, _, _ = _add_family_with_file(
            connection,
            job_id="old",
            key="ALT",
            capture="2026-07-23T14:00:00",
            relative_path=old_rel,
            payload=old_payload,
            root_kind="camera_archive",
        )
        incoming_family, _, _ = _add_family_with_file(
            connection,
            job_id="new",
            key="NEU",
            capture="2026-07-24T10:00:00",
            relative_path=incoming_rel,
            payload=incoming_payload,
            root_kind="shared_workspace",
        )
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision,applied_at,archived_at,timeline_model,
                   time_model_version
               ) VALUES ('archive','old',NULL,'parent',?,
                         '2026-07-23T00:00:00','2026-07-23T23:59:59',
                         0,?,'archived',?,?,?,0,1,?,?,
                         ?,2)""",
            (
                "Urlaub" if event_kind == "event" else "Ohne Ereignis",
                folder,
                NOW,
                NOW,
                event_kind,
                NOW,
                NOW,
                "continuous" if event_kind == "event" else "segments",
            ),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('archive',?,NULL,'date_range',?)""",
            (old_family, NOW),
        )
        if event_kind == "no_event":
            connection.execute(
                """INSERT INTO event_time_segments(
                       event_id,job_id,day_key,start_time,end_time,start_datetime,
                       end_datetime,source,created_at,updated_at
                   ) VALUES ('archive','old','2026-07-23','00:00','23:59',
                             '2026-07-23T00:00:00','2026-07-23T23:59:59',
                             'user',?,?)""",
                (NOW, NOW),
            )
        connection.commit()

    _materialize(archive_root / old_rel, old_payload)
    _materialize(work_root / incoming_rel, incoming_payload)
    return db, workspace, archive_root, folder, old_family, incoming_family, incoming_rel


def _move_staged_ssd_files_manually(
    db: Path,
    workspace: Path,
    archive_root: Path,
    change_request_id: str,
) -> list[dict]:
    reviews = get_event_change_files(db, change_request_id)
    work_root = workspace / "Arbeitsbereich"
    for row in reviews:
        if row["source_root_kind"] != "shared_workspace":
            continue
        staged = work_root / row["workspace_staging_path"]
        target = archive_root / row["new_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(staged.read_bytes())
    return reviews


@pytest.mark.parametrize("event_kind", ["event", "no_event"])
def test_0270_cross_job_archive_extension_finishes_on_canonical_event(
    tmp_path: Path, event_kind: str
):
    (
        db,
        workspace,
        archive_root,
        folder,
        old_family,
        incoming_family,
        incoming_rel,
    ) = _seed_archived_case(tmp_path, event_kind=event_kind)

    assert incoming_family in {
        int(row["family_id"]) for row in list_job_available_families(db, "new")
    }

    if event_kind == "event":
        preview = {
            "event_kind": "event",
            "event_name": "Urlaub",
            "parent_folder": folder,
            "child_folder": "",
            "uses_time_range": False,
            "preserve_day_folders": False,
            "start_date": "2026-07-23",
            "end_date": "2026-07-24",
            "start_time": "00:00",
            "end_time": "23:59",
            "selected_day_keys": [],
            "selected_family_ids": [old_family, incoming_family],
        }
        event_name = "Urlaub"
    else:
        preview = {
            "event_kind": "no_event",
            "event_name": "Ohne Ereignis",
            "parent_folder": folder,
            "child_folder": "",
            "uses_time_range": False,
            "preserve_day_folders": False,
            "start_date": "2026-07-23",
            "end_date": "2026-07-24",
            "start_time": "00:00",
            "end_time": "23:59",
            "selected_day_keys": ["2026-07-23", "2026-07-24"],
            "selected_family_ids": [old_family, incoming_family],
            "no_event_segments": [
                {"day_key": "2026-07-23", "start_time": "00:00", "end_time": "23:59"},
                {"day_key": "2026-07-24", "start_time": "00:00", "end_time": "23:59"},
            ],
        }
        event_name = "Ohne Ereignis"

    proposed = propose_event_change(
        db,
        "old",
        "archive",
        preview,
        event_name=event_name,
        archive_root=archive_root,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    assert proposed["staged_file_count"] == 1
    staging_event = workspace / "Arbeitsbereich" / "Später zuordnen" / "2026" / folder
    assert (staging_event / "Alle").is_dir()
    assert not (staging_event / "Sortiert").exists()
    assert not (staging_event / "Export").exists()
    reviews = _move_staged_ssd_files_manually(db, workspace, archive_root, cr_id)
    incoming_review = next(row for row in reviews if row["family_id"] == incoming_family)
    assert incoming_review["source_root_kind"] == "shared_workspace"
    assert incoming_review["workspace_staging_path"].startswith("Später zuordnen/")
    assert incoming_review["new_path"].endswith("/Alle/neu.JPG")

    confirm_event_change(db, cr_id)
    verified = verify_event_change(db, cr_id, archive_root)
    assert verified["complete"] is True
    result = finish_event_change(db, cr_id, archive_root, workspace)
    assert result["files_changed_by_app"] == 0

    with database_connection(db) as connection:
        owners = connection.execute(
            """SELECT ea.family_id,COALESCE(parent.id,assigned.id) AS root_id
               FROM event_assignments ea
               JOIN events assigned ON assigned.id=ea.event_id
               LEFT JOIN events parent ON parent.id=assigned.parent_event_id
               WHERE ea.family_id IN (?,?)
               ORDER BY ea.family_id""",
            (old_family, incoming_family),
        ).fetchall()
        assert {int(row["family_id"]): str(row["root_id"]) for row in owners} == {
            old_family: "archive",
            incoming_family: "archive",
        }
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM events WHERE linkage_kind='archived_manual'"
            ).fetchone()[0]
            == 0
        )
        if event_kind == "no_event":
            segments = connection.execute(
                """SELECT day_key,start_time,end_time
                   FROM event_time_segments
                   WHERE event_id='archive'
                   ORDER BY start_datetime"""
            ).fetchall()
            assert [tuple(row) for row in segments] == [
                ("2026-07-23", "00:00", "23:59"),
                ("2026-07-24", "00:00", "23:59"),
            ]

    context = get_event_edit_context(db, "old", "archive")
    assert set(context["assigned_family_ids"]) == {old_family, incoming_family}
    assert incoming_family not in {
        int(row["family_id"]) for row in list_job_available_families(db, "new")
    }
    assert not (workspace / "Arbeitsbereich" / incoming_rel).exists()
