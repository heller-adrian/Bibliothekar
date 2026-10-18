from __future__ import annotations

from app.archive_staging import staging_directory_name
from app.workspace_layout import shared_work_root

import errno
import hashlib
from pathlib import Path

import pytest

import app.archive_staging as archive_staging
from app.archive_change_assistant import build_archive_change_assistant
from app.archive_reversal import verify_archive_reversal
from app.archive_staging import ArchiveStagingError, cleanup_archive_change_staging
from app.database import database_connection, initialize_database
from app.event_change_apply import cancel_event_change, confirm_event_change
from app.event_change_request import propose_event_change
from app.event_structure import build_event_preview
from app.events_ui import EVENTS_HTML
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



def _provisioned_storage(workspace, language='legacy'):
    from app.storage_config import LEGACY_STORAGE_DEFAULTS, ENGLISH_STORAGE_DEFAULTS
    names=LEGACY_STORAGE_DEFAULTS if language=='legacy' else ENGLISH_STORAGE_DEFAULTS
    for name in names.values():(workspace/name).mkdir(exist_ok=True)


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


@pytest.mark.parametrize("root_language",["legacy","english"])
def test_0327_released_archive_group_counts_assets_and_honors_exclusion(tmp_path: Path, root_language):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _provisioned_storage(workspace,root_language)
    released_name="Freigewordene Archivdateien" if root_language=="legacy" else "Released Archive Files"
    ensure_workspace_layout(workspace)
    initialize_database(db)
    payload = b"camera"
    asset = b"xmp"
    export = b"export-copy"

    with database_connection(db) as connection:
        _seed_job(connection, "new")
        family_id, file_id = _add_family_file(
            connection,
            job_id="new",
            family_key="REL",
            capture="2026-07-25T11:38:13",
            relative_path=f"{released_name}/2026/2026-07-25/rel.JPG",
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
                f"{released_name}/2026/2026-07-25/rel.XMP",
                len(asset),
                _sha(asset),
                "CR_OLD",
                NOW,
                NOW,
            ),
        )

    from app.storage_config import storage_paths
    central = Path(storage_paths(workspace)["backup_root"])
    camera_path = central / f"{released_name}/2026/2026-07-25/rel.JPG"
    camera_path.parent.mkdir(parents=True, exist_ok=True)
    camera_path.write_bytes(payload)
    xmp_path = central / f"{released_name}/2026/2026-07-25/rel.XMP"
    xmp_path.write_bytes(asset)
    export_path = central / f"{released_name}/2026/2026-07-25/rel_Export.JPG"
    export_path.write_bytes(export)

    groups = list_global_released_archive_groups(
        db,
        workspace_path=workspace,
    )
    assert len(groups) == 1
    assert groups[0]["family_count"] == 1
    # Kameraoriginal + journalisierte XMP + später hinzugekommener Export.
    assert groups[0]["file_count"] == 3

    assert list_global_released_archive_groups(
        db,
        excluded_family_ids={family_id},
        workspace_path=workspace,
    ) == []


    with database_connection(db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    for physical in central.rglob("*"):
        if physical.is_file():assert physical.stat().st_size>0


@pytest.mark.parametrize("root_language",["legacy","english"])
def test_0327_archive_extension_stages_released_camera_and_xmp_from_global_stock(
    tmp_path: Path,
    root_language,
):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    _provisioned_storage(workspace,root_language)
    released_name="Freigewordene Archivdateien" if root_language=="legacy" else "Released Archive Files"
    ensure_workspace_layout(workspace)
    archive.mkdir()
    initialize_database(db)

    old_payload = b"archive-old"
    incoming_payload = b"released-camera"
    xmp_payload = b"released-xmp"

    old_rel = "2026/07.25 - Test/Alle/old.JPG"
    incoming_rel = (
        f"{released_name}/2026/2026-07-25/incoming.JPG"
    )
    xmp_rel = (
        f"{released_name}/2026/2026-07-25/incoming.XMP"
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

    from app.storage_config import storage_paths
    central = Path(storage_paths(workspace)["backup_root"])
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
            """SELECT asset_kind,old_path,new_path,source_root_kind,
                      workspace_original_path,released_archive_asset_id
               FROM event_change_asset_reviews
               WHERE change_request_id=?""",
            (cr_id,),
        ).fetchall()
    assert [(row["asset_kind"], row["old_path"]) for row in assets] == [
        ("xmp", xmp_rel)
    ]
    assert str(assets[0]["new_path"]).endswith("/Alle/incoming.XMP")
    assert str(assets[0]["source_root_kind"]) == "shared_workspace"
    assert str(assets[0]["workspace_original_path"]) == xmp_rel
    assert assets[0]["released_archive_asset_id"] is not None

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

    assistant = build_archive_change_assistant(
        db,
        archive,
        workspace,
        cr_id,
    )
    operation_kinds = [item["kind"] for item in assistant["operations"]]
    assert "move_archive_files" not in operation_kinds
    # Alle exists in the archive and must never be replaced as a folder.
    file_operations = [
        item for item in assistant["operations"]
        if item["kind"] == "copy_files"
    ]
    assert file_operations
    assert all(item["target"].endswith("/Alle") for item in file_operations)
    assert {"incoming.JPG", "incoming.XMP"}.issubset({
        name for item in file_operations for name in item["items"]
    })
    assert not any(
        "Alle" in item.get("items", [])
        for item in assistant["operations"]
        if item["kind"] == "copy_helper_folders"
    )

    helper_root = shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace))
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



    with database_connection(db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    for physical in central.rglob("*"):
        if physical.is_file():assert physical.stat().st_size>0


def test_0327_cross_dataset_staging_requires_explicit_choice_and_verifies_copy_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source.JPG"
    staged = tmp_path / "helper" / "source.JPG"
    payload = b"cross-dataset-payload"
    source.write_bytes(payload)
    expected_sha = _sha(payload)

    def exdev_link(*args, **kwargs):
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr(archive_staging.os, "link", exdev_link)

    with pytest.raises(ArchiveStagingError, match="TRANSFER_CHOICE_REQUIRED"):
        archive_staging._stage_verified_source(
            source,
            staged,
            expected_size=len(payload),
            expected_sha=expected_sha,
        )
    assert source.read_bytes() == payload
    assert not staged.exists()

    mode = archive_staging._stage_verified_source(
        source,
        staged,
        expected_size=len(payload),
        expected_sha=expected_sha,
        fallback_mode="copy",
    )
    assert mode == "copy"
    assert source.read_bytes() == payload
    assert staged.read_bytes() == payload

    staged.unlink()
    mode = archive_staging._stage_verified_source(
        source,
        staged,
        expected_size=len(payload),
        expected_sha=expected_sha,
        fallback_mode="move",
    )
    assert mode == "move"
    assert not source.exists()
    assert staged.read_bytes() == payload


def test_0327_ui_offers_copy_or_move_when_cross_dataset_hardlink_fails():
    assert "TRANSFER_CHOICE_REQUIRED" in EVENTS_HTML
    assert 'data-cr-transfer-choice="copy"' in EVENTS_HTML
    assert 'data-cr-transfer-choice="move"' in EVENTS_HTML
    assert "{transfer_mode:transferMode}" in EVENTS_HTML
    assert "options.payload || {}" in EVENTS_HTML
