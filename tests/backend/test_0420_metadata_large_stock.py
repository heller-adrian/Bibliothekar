from __future__ import annotations

from pathlib import Path
import hashlib
import json

import pytest

import app.metadata_correction as metadata_correction
from app.database import database_connection, initialize_database
from app.folder_import import partition_import_entries
from app.metadata import build_candidates
from app.metadata_correction import (
    MetadataCorrectionError,
    create_metadata_correction,
    scan_metadata_area,
)
from app.metadata_correction_ui import METADATA_CORRECTION_HTML


def test_0420_reimport_uses_original_sha_even_if_legacy_source_size_is_wrong():
    digest = hashlib.sha256(b"original-camera-bytes").hexdigest()
    entry = {
        "relative_path": "DCIM/IMG_0001.JPG",
        "size_bytes": len(b"original-camera-bytes"),
        "sha256": digest,
    }
    legacy_origin = {
        "job_id": "OLD",
        "source_volume_label": "SD alt",
        # Simulates migration 045 after an old metadata correction changed size.
        "size_bytes": 999999,
        "sha256": digest,
        "current_relative_path": "2026/2026-07-20/IMG.JPG",
        "original_filename": "IMG_0001.JPG",
    }

    new, duplicates, details = partition_import_entries(
        [entry],
        known_hashes={(999999, digest)},
        duplicate_origins={(999999, digest): legacy_origin},
        known_sha256={digest},
        duplicate_origins_by_sha={digest: legacy_origin},
    )

    assert new == []
    assert duplicates == [entry]
    assert details[0]["existing_job_id"] == "OLD"


def test_0420_candidates_expose_file_create_date_german_label_and_trust():
    candidates = build_candidates(
        {
            "EXIF:ExifIFD:DateTimeOriginal": "2026:07:20 14:15:30",
            "File:System:FileCreateDate": "2026:07:20 14:15:31+02:00",
        },
        "jpeg",
    )
    by_type = {row["source_type"]: row for row in candidates}

    assert by_type["DateTimeOriginal"]["label_de"] == "Aufnahmezeit"
    assert by_type["DateTimeOriginal"]["trust_label"] == "hoch"
    assert by_type["DateTimeOriginal"]["trust_score"] > by_type["FileCreateDate"]["trust_score"]
    assert by_type["FileCreateDate"]["label_de"] == "Datei-Erstellungszeit"
    assert by_type["FileCreateDate"]["technical_tag"] == "File:System:FileCreateDate"


def test_0420_explicit_source_tag_is_revalidated_before_write(tmp_path: Path, monkeypatch):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    source = workspace / "Metadatenkorrektur" / "Allgemein" / "A.JPG"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"photo")
    initialize_database(database)

    candidate = {
        "tag_name": "EXIF:ExifIFD:DateTimeOriginal",
        "source_type": "DateTimeOriginal",
        "normalized_datetime": "2026-07-20T14:15:30",
        "usable": True,
        "confidence": "high",
    }
    scan = {
        "area": "general",
        "files": [{
            "relative_path": "A.JPG",
            "filename": "A.JPG",
            "media_type": "jpeg",
            "selected_capture_time": "2026-07-20T14:15:30",
            "selected_capture_source": candidate["tag_name"],
            "capture_time_confidence": "high",
            "review_required": False,
            "metadata_candidates": [candidate],
            "filename_suggestion": None,
        }],
    }
    monkeypatch.setattr(metadata_correction, "scan_metadata_area", lambda **_: scan)

    task = create_metadata_correction(
        database,
        area="general",
        relative_path="A.JPG",
        proposed_datetime="2026-07-20T14:15:30",
        proposal_source_tag=candidate["tag_name"],
        workspace_root=workspace,
        library_id="main",
    )
    assert task["proposal_source"] == "metadata"
    assert task["detected"]["proposal_source_tag"] == candidate["tag_name"]

    with pytest.raises(MetadataCorrectionError, match="Quelltyp"):
        create_metadata_correction(
            database,
            area="general",
            relative_path="A.JPG",
            proposed_datetime="2026-07-21T14:15:30",
            proposal_source_tag=candidate["tag_name"],
            workspace_root=workspace,
            library_id="main",
        )


def test_0420_completed_correction_keeps_original_metadata_visible(tmp_path: Path, monkeypatch):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    source = workspace / "Metadatenkorrektur" / "Allgemein" / "A.JPG"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"photo")
    initialize_database(database)

    before = {
        "selected_capture_time": "2011-01-02T03:04:05",
        "selected_capture_source": "EXIF:ExifIFD:DateTimeOriginal",
        "capture_time_confidence": "conflict",
        "metadata_candidates": [{"tag_name": "EXIF:ExifIFD:DateTimeOriginal"}],
    }
    now = "2026-10-07T13:00:00+02:00"
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO metadata_corrections(
                   id,area,status,source_path,source_relative_path,source_filename,
                   source_size_bytes,source_sha256,media_type,detected_json,
                   proposed_datetime,proposal_source,output_path,output_size_bytes,
                   output_sha256,verification_json,error_message,created_at,updated_at,
                   completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "META_OLD",
                "general",
                "completed",
                str(source),
                "A.JPG",
                "A.JPG",
                5,
                hashlib.sha256(b"photo").hexdigest(),
                "jpeg",
                json.dumps({"before_metadata": before}),
                "2026-07-20T14:15:30",
                "manual",
                str(source),
                5,
                hashlib.sha256(b"photo").hexdigest(),
                "{}",
                None,
                now,
                now,
                now,
            ),
        )

    monkeypatch.setattr(
        metadata_correction,
        "analyze_tree",
        lambda root, include_other=False: {
            "files": [{
                "relative_path": "A.JPG",
                "filename": "A.JPG",
                "media_type": "jpeg",
                "selected_capture_time": "2026-07-20T14:15:30",
                "selected_capture_source": "EXIF:ExifIFD:DateTimeOriginal",
                "capture_time_confidence": "high",
                "review_required": False,
                "metadata_candidates": [],
            }],
            "families": [],
        },
    )
    scan = scan_metadata_area(
        area="general",
        workspace_root=workspace,
        library_id="main",
        database_path=database,
    )

    assert scan["files"][0]["original_metadata"]["before_metadata"] == before


def test_0420_ui_has_opt_in_selection_and_per_file_source_values():
    html = METADATA_CORRECTION_HTML

    assert 'id="meta-select-mode"' in html
    assert 'id="meta-select-all" type="button" hidden' in html
    assert "const checkbox=state.selectionMode" in html
    assert "if(state.selectionMode)" in html
    assert "event.shiftKey" in html
    assert 'id="meta-bulk-source"' in html
    assert "Für jede Datei wird ihr eigener Wert des gewählten Metadaten-Tags verwendet." in html
    assert "candidateForType(file,type)" in html
    assert "/api/metadata-correction/correct-batch" in html
    assert "source_type:type" in html
    assert "Bevorzugter Metadatenkandidat" in html
    assert "data-meta-use-candidate" in html
    assert "Weitere Metadaten" in html
    assert "others.slice(0,3)" in html
    assert "Weitere anzeigen (" in html
    assert "Ursprüngliche Metadaten vor der Korrektur" in html
    assert "/api/metadata-correction/general/reintegrate" in html



def test_0420_prevalidated_record_skips_second_full_scan(tmp_path: Path, monkeypatch):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    source = workspace / "Metadatenkorrektur" / "Allgemein" / "B.JPG"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"photo-b")
    initialize_database(database)

    candidate = {
        "tag_name": "EXIF:ExifIFD:DateTimeOriginal",
        "source_type": "DateTimeOriginal",
        "normalized_datetime": "2026-07-22T09:10:11",
        "usable": True,
        "confidence": "high",
    }
    row = {
        "relative_path": "B.JPG",
        "filename": "B.JPG",
        "media_type": "jpeg",
        "selected_capture_time": "2026-07-22T09:10:11",
        "selected_capture_source": candidate["tag_name"],
        "capture_time_confidence": "high",
        "review_required": False,
        "metadata_candidates": [candidate],
        "filename_suggestion": None,
    }
    monkeypatch.setattr(
        metadata_correction,
        "scan_metadata_area",
        lambda **_: (_ for _ in ()).throw(AssertionError("Vollscan darf nicht erneut laufen")),
    )

    task = create_metadata_correction(
        database,
        area="general",
        relative_path="B.JPG",
        proposed_datetime="2026-07-22T09:10:11",
        proposal_source_tag=candidate["tag_name"],
        workspace_root=workspace,
        library_id="main",
        _prevalidated_row=row,
        _prevalidated_source=source,
    )
    assert task["status"] == "prepared"


def test_0420_general_day_stock_reuses_managed_import_and_blocks_known_provenance():
    source = Path("app/main.py").read_text(encoding="utf-8")

    assert '"/api/metadata-correction/correct-batch"' in source
    assert "_prevalidated_row=row" in source
    assert '"metadata_general_import"' in source
    assert "managed_metadata_import = managed_multiple_import or managed_general_import" in source
    assert "allow_workspace_source=managed_metadata_import" in source
    assert "known_camera_sha = known_original_sha | known_current_sha" in source
    assert "Es wird keine neue Sicherung/Provenienz angelegt" in source
    assert 'operation="metadata_general_import"' in source
