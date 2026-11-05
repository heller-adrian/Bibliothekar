from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.main as main
import app.metadata_correction as metadata_correction
from app.database import database_connection, initialize_database, list_global_tasks
from app.metadata_correction import (
    MetadataCorrectionError,
    create_metadata_correction,
    execute_metadata_correction,
    get_metadata_correction,
)
from app.metadata_correction_ui import METADATA_CORRECTION_HTML


def _general_scan(filename: str) -> dict:
    return {
        "area": "general",
        "summary": {"file_count": 1, "needs_attention": 0, "filename_suggestions": 1},
        "files": [{
            "relative_path": filename,
            "filename": filename,
            "media_type": "jpeg",
            "selected_capture_time": "2026-07-21T17:28:08+03:00",
            "selected_capture_source": "EXIF:DateTimeOriginal",
            "capture_time_confidence": "high",
            "metadata_candidates": [{
                "tag_name": "EXIF:DateTimeOriginal",
                "raw_value": "2026:07:21 17:28:08+03:00",
                "normalized_datetime": "2026-07-21T17:28:08+03:00",
                "confidence": "high",
                "usable": True,
            }],
            "filename_suggestion": {
                "date": "2026-07-21",
                "time": "17:28:08",
                "datetime": "2026-07-21T17:28:08",
            },
            "preferred_suggestion": {
                "date": "2026-07-21",
                "time": "17:28:08",
                "datetime": "2026-07-21T17:28:08",
            },
        }],
    }


def _general_file(workspace: Path, filename: str = "20260721_172808_Fuji-X-E5.JPG") -> Path:
    path = workspace / "Metadatenkorrektur" / "Allgemein" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpeg-payload")
    return path


def test_0332_ui_preserves_seconds_and_uses_direct_correction():
    assert "Metadaten ändern" in METADATA_CORRECTION_HTML
    assert "/api/metadata-correction/correct" in METADATA_CORRECTION_HTML
    assert ".slice(0,8)" in METADATA_CORRECTION_HTML
    assert ".slice(0,5)" not in METADATA_CORRECTION_HTML


def test_0332_direct_general_correction_keeps_before_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(database)
    source = _general_file(workspace)

    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: _general_scan(source.name),
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

    completed = execute_metadata_correction(
        database,
        area="general",
        relative_path=source.name,
        proposed_datetime="2026-07-21T17:30:08",
        workspace_root=workspace,
        library_id="main",
    )

    assert completed["status"] == "completed"
    assert completed["proposed_datetime"] == "2026-07-21T17:30:08"
    before = completed["detected"]["before_metadata"]
    assert before["selected_capture_time"] == "2026-07-21T17:28:08+03:00"
    assert before["selected_capture_source"] == "EXIF:DateTimeOriginal"
    assert before["capture_time_confidence"] == "high"
    assert source.is_file()


def test_0332_new_correction_supersedes_old_unwritten_duplicate(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(database)
    source = _general_file(workspace)

    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: _general_scan(source.name),
    )

    first = create_metadata_correction(
        database,
        area="general",
        relative_path=source.name,
        proposed_datetime="2026-07-21T17:29:08",
        workspace_root=workspace,
        library_id="main",
    )
    second = create_metadata_correction(
        database,
        area="general",
        relative_path=source.name,
        proposed_datetime="2026-07-21T17:30:08",
        workspace_root=workspace,
        library_id="main",
    )

    assert get_metadata_correction(database, str(first["id"]))["status"] == "cancelled"
    assert get_metadata_correction(database, str(second["id"]))["status"] == "prepared"


def test_0332_global_metadata_tasks_are_grouped_by_area(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)

    rows = [
        ("META_A", "general", "prepared", "/a.jpg", "a.jpg", None),
        ("META_B", "general", "blocked", "/b.jpg", "b.jpg", "blockiert"),
        ("META_C", "library", "prepared", "/c.jpg", "c.jpg", None),
    ]
    with database_connection(database) as connection:
        for correction_id, area, status, path, filename, error in rows:
            connection.execute(
                """INSERT INTO metadata_corrections(
                       id,area,status,source_path,source_relative_path,source_filename,
                       source_size_bytes,source_sha256,media_type,detected_json,
                       proposed_datetime,proposal_source,verification_json,error_message,
                       created_at,updated_at
                   )
                   VALUES (?,?,?,?,?,?,1,'sha','jpeg','{}',
                           '2026-07-21T17:30:08','manual','{}',?,
                           '2026-10-03T18:00:00+02:00','2026-10-03T18:00:00+02:00')""",
                (correction_id, area, status, path, filename, filename, error),
            )

    tasks = [
        task for task in list_global_tasks(database)
        if task.get("kind") == "metadata_correction"
    ]
    # Bibliothekskorrekturen werden ab 0.33.5 über den fachlichen
    # Ohne-Datum-/Prüffall-Task gebündelt und hier nicht doppelt angezeigt.
    assert len(tasks) == 1
    assert tasks[0]["metadata_area"] == "general"
    assert tasks[0]["count"] == 1
    assert tasks[0]["correction_count"] == 2
    assert tasks[0]["blocked_count"] == 1


def test_0332_metadata_api_expected_error_is_not_internal_server_error(monkeypatch):
    context = SimpleNamespace(
        library_id="main",
        display_name="Main Library",
        database_path=Path("/tmp/unused.sqlite3"),
        workspace_root=Path("/tmp/workspace"),
    )
    monkeypatch.setattr(main, "current_library_context", lambda: context)

    def fail(*args, **kwargs):
        raise MetadataCorrectionError("gezielter Testfehler")

    monkeypatch.setattr(main, "create_metadata_correction", fail)

    with pytest.raises(HTTPException) as captured:
        # Test only route error translation; F14 admission has its own fixture tests.
        main.api_prepare_metadata_correction.__wrapped__({
            "area": "general",
            "relative_path": "test.jpg",
            "proposed_datetime": "2026-07-21T17:30:08",
        })

    assert captured.value.status_code == 422
    assert captured.value.detail == "gezielter Testfehler"
