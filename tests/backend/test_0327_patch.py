from __future__ import annotations

import hashlib
from pathlib import Path

from app.archive_reversal import verify_archive_reversal
from app.archive_staging import cleanup_archive_change_staging
from app.database import database_connection, initialize_database
from app.event_change_apply import cancel_event_change, confirm_event_change
from app.event_change_request import propose_event_change
from app.event_structure import build_event_preview
from app.planning import list_global_released_archive_groups
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-02T14:30:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed_job(connection, job_id: str) -> None:
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,source_volume_label,
               created_at,updated_at
           ) VALUES (?, 'sd_import','manual','completed','done','folder_import',?,?,?)""",
        (job_id, job_id.upper(), NOW, NOW),
    )


def _add_family_file(
    connection,
    *,
    job_id: str,
    family_key: str,
    capture: str,
    relative_path: str,
    payload: bytes,
    root_kind: str,
) -> tuple[int, int]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, family_key, family_key, capture),
        ).lastrowid
    )
    digest = _sha(payload)
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
    return family_id, file_id


def _family(family_id: int, capture: str, *, file_count: int = 2) -> dict:
    return {
        "family_id": family_id,
        "selected_capture_time": capture,
        "day_key": capture[:10],
        "has_date": True,
        "file_count": file_count,
        "total_size_bytes": 1,
        "review_required_count": 0,
    }


def test_0327_time_range_trims_selected_day_stock_instead_of_rejecting_it():
    preview = build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Test",
            "start_date": "2026-07-25",
            "end_date": "2026-07-25",
            "start_time": "10:00",
            "end_time": "23:59",
            "uses_time_range": True,
            "preserve_day_folders": False,
            "selected_day_keys": ["2026-07-25"],
            "selected_family_ids": [1, 2, 3],
        },
        [
            _family(1, "2026-07-25T09:06:01"),
            _family(2, "2026-07-25T10:47:31"),
            _family(3, "2026-07-25T11:38:13"),
        ],
    )

    assert preview["selected_family_ids"] == [2, 3]
    assert preview["selected_family_count"] == 2
    assert preview["selected_file_count"] == 4


def test_0327_released_archive_group_counts_assets_and_honors_exclusion(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    payload = b"camera"
    asset = b"xmp"

    with database_connection(db) as connection:
        _seed_job(connection, "new")
        family_id, file_id = _add_family_file(
            connection,
            job_id="new",
            family_key="REL",
            capture="2026-07-25T11:38:13",
            relative_path="Freigewordene Archivdateien/2026/2026-07-25/rel.JPG",
            payload=payload,
            root_kind="shared_workspace",
        )
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES (?,?,?,?,?,1)""",
            (
                "new",
                family_id,
                "2026-07-25T00:00:00",
                "2026-07-25T23:59:59",
                NOW,
            ),
        )
        connection.execute(
            """INSERT INTO released_archive_assets(
                   job_id,family_id,source_file_id,asset_kind,current_relative_path,
                   size_bytes,sha256,origin_change_request_id,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                "new",
                family_id,
                file_id,
                "xmp",
                "Freigewordene Archivdateien/2026/2026-07-25/rel.XMP",
                len(asset),
                _sha(asset),
                "CR_OLD",
                NOW,
                NOW,
            ),
        )

    groups = list_global_released_archive_groups(db)
    assert len(groups) == 1
    assert groups[0]["family_count"] == 1
    assert groups[0]["file_count"] == 2

    assert list_global_released_archive_groups(
        db,
        excluded_family_ids={family_id},
    ) == []


def test_0327_archive_extension_stages_released_camera_and_xmp_from_global_stock(
    tmp_path: Path,
):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    archive.mkdir()
    initialize_database(db)

    old_payload = b"archive-old"
    incoming_payload = b"released-camera"
    xmp_payload = b"released-xmp"

    old_rel = "2026/07.25 - Test/Alle/old.JPG"
    incoming_rel = (
        "Freigewordene Archivdateien/2026/2026-07-25/incoming.JPG"
    )
    xmp_rel = (
        "Freigewordene Archivdateien/2026/2026-07-25/incoming.XMP"
    )

    with database_connection(db) as connection:
        _seed_job(connection, "old")
        _seed_job(connection, "new")
        old_family, _ = _add_family_file(
            connection,
            job_id="old",
            family_key="OLD",
            capture="2026-07-25T10:30:00",
            relative_path=old_rel,
            payload=old_payload,
            root_kind="camera_archive",
        )
        incoming_family, incoming_file_id = _add_family_file(
            connection,
            job_id="new",
            family_key="NEW",
            capture="2026-07-25T11:38:13",
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
               ) VALUES (
                   'archive','old',NULL,'parent','Test',
                   '2026-07-25T00:00:00','2026-07-25T23:59:59',
                   0,'07.25 - Test','archived',?,?, 'event',0,1,?,?, 'continuous',2
               )""",
            (NOW, NOW, NOW, NOW),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('archive',?,NULL,'date_time_range',?)""",
            (old_family, NOW),
        )
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES (?,?,?,?,?,1)""",
            (
                "new",
                incoming_family,
                "2026-07-25T00:00:00",
                "2026-07-25T23:59:59",
                NOW,
            ),
        )
        connection.execute(
            """INSERT INTO released_archive_assets(
                   job_id,family_id,source_file_id,asset_kind,current_relative_path,
                   size_bytes,sha256,origin_change_request_id,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                "new",
                incoming_family,
                incoming_file_id,
                "xmp",
                xmp_rel,
                len(xmp_payload),
                _sha(xmp_payload),
                "CR_OLD",
                NOW,
                NOW,
            ),
        )

    archive_file = archive / old_rel
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    archive_file.write_bytes(old_payload)

    central = workspace / "SD-Kartensicherungen"
    incoming_path = central / incoming_rel
    incoming_path.parent.mkdir(parents=True, exist_ok=True)
    incoming_path.write_bytes(incoming_payload)
    xmp_path = central / xmp_rel
    xmp_path.write_bytes(xmp_payload)

    preview = {
        "event_kind": "event",
        "event_name": "Test",
        "parent_folder": "07.25 - Test",
        "child_folder": "",
        "uses_time_range": True,
        "preserve_day_folders": False,
        "start_date": "2026-07-25",
        "end_date": "2026-07-25",
        "start_time": "10:00",
        "end_time": "23:59",
        "selected_day_keys": ["2026-07-25"],
        "selected_family_ids": [old_family, incoming_family],
    }
    proposed = propose_event_change(
        db,
        "old",
        "archive",
        preview,
        event_name="Test",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = str(proposed["change_request_id"])

    with database_connection(db) as connection:
        assets = connection.execute(
            """SELECT asset_kind,old_path,new_path
               FROM event_change_asset_reviews
               WHERE change_request_id=?""",
            (cr_id,),
        ).fetchall()
    assert [(row["asset_kind"], row["old_path"]) for row in assets] == [
        ("xmp", xmp_rel)
    ]
    assert str(assets[0]["new_path"]).endswith("/Alle/incoming.XMP")

    confirmed = confirm_event_change(
        db,
        cr_id,
        archive,
        workspace,
    )
    preparation = confirmed["preparation"]
    assert preparation["staged_file_count"] == 2
    assert preparation["staged_camera_file_count"] == 1
    assert preparation["staged_asset_count"] == 1

    helper_root = workspace / "Arbeitsbereich" / "Später zuordnen"
    assert (
        helper_root
        / "2026"
        / "07.25 - Test"
        / "Alle"
        / "incoming.JPG"
    ).is_file()
    assert (
        helper_root
        / "2026"
        / "07.25 - Test"
        / "Alle"
        / "incoming.XMP"
    ).is_file()

    assert incoming_path.is_file()
    assert xmp_path.is_file()

    reversal_check = verify_archive_reversal(
        db, archive, workspace, cr_id
    )
    assert reversal_check["complete"], reversal_check

    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["status"] == "abgebrochen"
    assert cancelled["reversal_required"] is False
    assert incoming_path.is_file()
    assert xmp_path.is_file()
    assert not (
        helper_root
        / "2026"
        / "07.25 - Test"
        / "Alle"
        / "incoming.JPG"
    ).exists()
    assert not (
        helper_root
        / "2026"
        / "07.25 - Test"
        / "Alle"
        / "incoming.XMP"
    ).exists()
