from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.metadata_correction as metadata_correction
from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    get_event_edit_context,
    initialize_database,
    list_global_tasks,
)
from app.event_naming import (
    legacy_naming_for_existing_event,
    render_event_folder_name,
    render_no_event_folder_name,
)
from app.event_structure import build_event_preview
from app.metadata_correction import (
    MetadataCorrectionError,
    apply_metadata_correction,
    create_metadata_correction,
    detect_filename_datetime,
    get_metadata_correction,
)


def _family(
    family_id: int,
    capture: str,
    *,
    files: int = 2,
) -> dict:
    return {
        "family_id": family_id,
        "family_key": f"F{family_id}",
        "original_stem": f"IMG_{family_id:04d}",
        "selected_capture_time": capture,
        "capture_time_confidence": "high",
        "has_date": True,
        "day_key": capture[:10],
        "file_count": files,
        "total_size_bytes": 100,
        "review_required_count": 0,
    }


def test_0330_custom_event_folder_naming():
    assert render_event_folder_name(
        event_name="Urlaub",
        start_date="2026-07-20",
        end_date="2026-07-21",
        start_time="14:00",
        end_time="18:30",
        uses_time_range=True,
        naming={
            "no_event_label": "Nicht zugeordnet",
            "date_mode": "range",
            "include_year": True,
            "include_time": True,
        },
    ) == "2026-07-20 14-00–2026-07-21 18-30 - Urlaub"

    assert render_event_folder_name(
        event_name="Urlaub",
        start_date="2026-07-20",
        end_date="2026-07-21",
        start_time="00:00",
        end_time="23:59",
        uses_time_range=False,
        naming={},
    ) == "07-20 - Urlaub"

    assert render_no_event_folder_name(
        "2026-07",
        {"no_event_label": "Nicht zugeordnet"},
    ) == "07 - Nicht zugeordnet"


def test_0330_legacy_events_keep_old_policy_but_remain_editable():
    normal_policy = legacy_naming_for_existing_event(
        event_kind="event",
        folder_name="07-20 - Alt",
        event_name="Alt",
    )
    assert render_event_folder_name(
        event_name="Neu",
        start_date="2026-07-21",
        end_date="2026-07-21",
        start_time="12:00",
        end_time="14:00",
        uses_time_range=True,
        naming=normal_policy,
    ) == "07-21 - Neu"

    no_event_policy = legacy_naming_for_existing_event(
        event_kind="no_event",
        folder_name="07 - Ohne Ereignis",
        event_name="07 - Ohne Ereignis",
    )
    assert render_no_event_folder_name(
        "2026-08",
        no_event_policy,
    ) == "08 - Ohne Ereignis"


def test_0330_no_event_preview_uses_library_label():
    preview = build_event_preview(
        {
            "event_kind": "no_event",
            "no_event_segments": [
                {
                    "day_key": "2026-07-19",
                    "start_time": "00:00",
                    "end_time": "17:59",
                },
                {
                    "day_key": "2026-07-19",
                    "start_time": "19:31",
                    "end_time": "23:59",
                },
            ],
            "preserve_day_folders": True,
            "folder_naming": {
                "no_event_label": "Nicht zugeordnet",
                "date_mode": "start",
                "include_year": False,
                "include_time": False,
            },
        },
        [
            _family(1, "2026-07-19T12:00:00"),
            _family(2, "2026-07-19T22:00:00"),
        ],
    )
    assert preview["event_name"] == "07 - Nicht zugeordnet"
    assert preview["parent_folder"] == "07 - Nicht zugeordnet"
    assert len(preview["no_event_segments"]) == 2
    # Two logical time segments still share one physical day folder.
    assert preview["structure_text"].count("2026-07-19") >= 1


def test_0330_naming_snapshot_is_persisted_per_event(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    create_job(
        database,
        job_id="JOB",
        kind="simulation",
        trigger_type="manual",
        operation="folder_import",
    )
    with database_connection(database) as connection:
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES ('JOB','F1','IMG_1','complete',
                       '2026-07-20T12:00:00','high')"""
        ).lastrowid)

    preview = build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Urlaub",
            "start_date": "2026-07-20",
            "end_date": "2026-07-20",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": True,
            "preserve_day_folders": False,
            "selected_family_ids": [family_id],
            "folder_naming": {
                "no_event_label": "Rest",
                "date_mode": "start",
                "include_year": True,
                "include_time": False,
            },
        },
        [_family(family_id, "2026-07-20T12:00:00")],
    )
    created = create_planned_event(database, "JOB", preview)
    event_id = str(created["parent_event"]["id"])

    with database_connection(database) as connection:
        row = connection.execute(
            "SELECT folder_name,folder_naming_json FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
    assert row["folder_name"] == "2026-07-20 - Urlaub"
    assert json.loads(row["folder_naming_json"])["include_year"] is True

    context = get_event_edit_context(database, "JOB", event_id)
    assert context["event"]["folder_naming"]["include_year"] is True


def test_0330_filename_datetime_detection():
    camera = detect_filename_datetime("20260720_141530_Fuji-X-E5.JPG")
    assert camera is not None
    assert camera["datetime"] == "2026-07-20T14:15:30"
    assert camera["requires_time"] is False

    whatsapp = detect_filename_datetime("IMG-20260720-WA0042.jpg")
    assert whatsapp is not None
    assert whatsapp["date"] == "2026-07-20"
    assert whatsapp["datetime"] is None
    assert whatsapp["requires_time"] is True

    assert detect_filename_datetime("IMG-20261340-WA0042.jpg") is None


def _fake_scan(relative_path: str) -> dict:
    return {
        "area": "general",
        "paths": {},
        "summary": {"file_count": 1},
        "files": [{
            "relative_path": relative_path,
            "filename": Path(relative_path).name,
            "media_type": "jpeg",
            "selected_capture_time": None,
            "selected_capture_source": None,
            "capture_time_confidence": "missing",
            "review_required": True,
            "metadata_candidates": [],
            "filename_suggestion": {
                "rule": "camera_yyyymmdd_hhmmss",
                "date": "2026-07-20",
                "time": "14:15:30",
                "datetime": "2026-07-20T14:15:30",
                "requires_time": False,
                "confidence": "high",
                "source": "filename",
            },
        }],
    }


def _metadata_input(workspace: Path, filename: str) -> Path:
    source = workspace / "Metadatenkorrektur" / "Allgemein" / filename
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"original-image-payload")
    return source


def test_0330_metadata_correction_writes_only_verified_output(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(database)
    source = _metadata_input(workspace, "20260720_141530_Test.JPG")

    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: _fake_scan(source.name),
    )
    task = create_metadata_correction(
        database,
        area="general",
        relative_path=source.name,
        proposed_datetime="2026-07-20T14:15:30",
        workspace_root=workspace,
        library_id="main",
    )
    monkeypatch.setattr(
        metadata_correction,
        "write_metadata_datetime",
        lambda path, media_type, value: None,
    )
    monkeypatch.setattr(
        metadata_correction,
        "verify_metadata_datetime",
        lambda path, expected: {
            "expected_datetime": expected,
            "matching_tags": [{"tag": "EXIF:DateTimeOriginal", "value": expected}],
            "observed_tags": [],
        },
    )

    completed = apply_metadata_correction(
        database,
        str(task["id"]),
        workspace_root=workspace,
        library_id="main",
    )
    output = Path(str(completed["output_path"]))
    assert completed["status"] == "completed"
    assert output.is_file()
    assert output.suffix == ".JPG"
    assert source.exists()
    assert output == source
    assert output.read_bytes() == b"original-image-payload"


def test_0330_metadata_write_failure_keeps_input_and_becomes_task(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(database)
    source = _metadata_input(workspace, "20260720_141530_Blocked.JPG")

    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: _fake_scan(source.name),
    )
    task = create_metadata_correction(
        database,
        area="general",
        relative_path=source.name,
        proposed_datetime="2026-07-20T14:15:30",
        workspace_root=workspace,
        library_id="main",
    )

    def fail_write(path: Path, media_type: str, value: str) -> None:
        raise MetadataCorrectionError("Schreibtest absichtlich blockiert.")

    monkeypatch.setattr(metadata_correction, "write_metadata_datetime", fail_write)

    with pytest.raises(MetadataCorrectionError):
        apply_metadata_correction(
            database,
            str(task["id"]),
            workspace_root=workspace,
            library_id="main",
        )

    blocked = get_metadata_correction(database, str(task["id"]))
    assert blocked["status"] == "blocked"
    assert source.is_file()
    tasks = list_global_tasks(database)
    assert any(
        item.get("kind") == "metadata_correction"
        and item.get("metadata_correction_id") == task["id"]
        for item in tasks
    )
