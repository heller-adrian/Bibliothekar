from __future__ import annotations

from pathlib import Path
import re

import app.metadata_correction as metadata_correction
from app.database import initialize_database
from app.metadata_correction import execute_metadata_correction


def _general_scan(filename: str) -> dict:
    return {
        "area": "general",
        "summary": {"file_count": 1, "needs_attention": 0, "filename_suggestions": 0},
        "files": [{
            "relative_path": filename,
            "filename": filename,
            "media_type": "jpeg",
            "selected_capture_time": "2026-07-21T17:28:08+03:00",
            "selected_capture_source": "EXIF:DateTimeOriginal",
            "capture_time_confidence": "high",
            "metadata_candidates": [],
            "filename_suggestion": None,
            "preferred_suggestion": {
                "date": "2026-07-21",
                "time": "17:28:08",
                "datetime": "2026-07-21T17:28:08",
            },
        }],
    }


def test_0333_metadata_correction_never_uses_copy2():
    source = Path("app/metadata_correction.py").read_text(encoding="utf-8")
    assert re.search(r"^\s*shutil\.copy2\(", source, re.MULTILINE) is None
    assert len(re.findall(r"^\s*shutil\.copyfile\(", source, re.MULTILINE)) >= 3


def test_0333_general_correction_works_when_copy2_is_forbidden(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    source = (
        workspace
        / "Metadatenkorrektur"
        / "Allgemein"
        / "20260721_172808_Fuji-X-E5.JPG"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"jpeg-payload")
    initialize_database(database)

    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: _general_scan(source.name),
    )

    def forbidden_copy2(*args, **kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(metadata_correction.shutil, "copy2", forbidden_copy2)
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
    assert source.read_bytes() == b"jpeg-payload"
