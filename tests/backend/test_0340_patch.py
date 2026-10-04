from __future__ import annotations

from pathlib import Path

import pytest

from app import main
import app.metadata_correction as metadata_correction
from app.metadata_correction import (
    MetadataCorrectionError,
    apply_multiple_metadata_correction,
    metadata_area_paths,
    preview_multiple_metadata_correction,
    scan_metadata_area,
)
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.workspace_layout import ensure_workspace_layout


def _fake_multiple_analysis(root: Path, include_other: bool = False) -> dict:
    root = Path(root)
    rows = [
        {
            "relative_path": "A.JPG",
            "filename": "A.JPG",
            "family_key": "A",
            "media_type": "jpeg",
            "selected_capture_time": "2026-07-21T10:00:00+03:00",
            "selected_capture_source": "EXIF:DateTimeOriginal",
            "capture_time_confidence": "high",
            "review_required": False,
        },
        {
            "relative_path": "B.MP4",
            "filename": "B.MP4",
            "family_key": "B",
            "media_type": "video",
            "selected_capture_time": "2026-07-21T10:05:30+03:00",
            "selected_capture_source": "QuickTime:CreateDate",
            "capture_time_confidence": "high",
            "review_required": False,
        },
    ]
    return {
        "files": rows,
        "families": [
            {
                "family_key": row["family_key"],
                "selected_capture_time": row["selected_capture_time"],
                "capture_time_confidence": "high",
            }
            for row in rows
        ],
    }


def test_0340_multiple_folder_is_created_next_to_general(tmp_path: Path):
    ensure_workspace_layout(tmp_path)
    general = tmp_path / "Metadatenkorrektur" / "Allgemein"
    multiple = tmp_path / "Metadatenkorrektur" / "Mehrfachkorrektur"
    assert general.is_dir()
    assert multiple.is_dir()

    paths = metadata_area_paths(
        area="multiple",
        workspace_root=tmp_path,
        library_id="main",
        create=True,
    )
    assert paths["root"] == multiple.resolve()


def test_0340_preview_applies_constant_offset_to_every_file(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "Metadatenkorrektur" / "Mehrfachkorrektur"
    root.mkdir(parents=True)
    (root / "A.JPG").write_bytes(b"photo")
    (root / "B.MP4").write_bytes(b"video")
    monkeypatch.setattr(metadata_correction, "analyze_tree", _fake_multiple_analysis)

    preview = preview_multiple_metadata_correction(
        workspace_root=tmp_path,
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-07-21T12:30:00",
    )

    assert preview["offset_seconds"] == 9000
    assert preview["reference_old_datetime"] == "2026-07-21T10:00:00"
    assert preview["reference_new_datetime"] == "2026-07-21T12:30:00"
    by_name = {row["filename"]: row for row in preview["files"]}
    assert by_name["A.JPG"]["new_datetime"] == "2026-07-21T12:30:00"
    assert by_name["B.MP4"]["new_datetime"] == "2026-07-21T12:35:30"
    assert len(preview["preview_fingerprint"]) == 64


def test_0340_preview_does_not_write_and_apply_writes_all_files(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "Metadatenkorrektur" / "Mehrfachkorrektur"
    root.mkdir(parents=True)
    first = root / "A.JPG"
    second = root / "B.MP4"
    first.write_bytes(b"photo")
    second.write_bytes(b"video")
    monkeypatch.setattr(metadata_correction, "analyze_tree", _fake_multiple_analysis)

    writes: list[tuple[str, str, str]] = []

    def fake_write(path: Path, media_type: str, value: str) -> None:
        writes.append((Path(path).name, media_type, value))
        Path(path).write_bytes(Path(path).read_bytes() + ("|" + value).encode())

    monkeypatch.setattr(metadata_correction, "write_metadata_datetime", fake_write)
    monkeypatch.setattr(
        metadata_correction,
        "verify_metadata_datetime",
        lambda path, expected: {
            "expected_datetime": expected,
            "matching_tags": [{"tag": "test", "value": expected}],
            "observed_tags": [],
        },
    )

    preview = preview_multiple_metadata_correction(
        workspace_root=tmp_path,
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-07-21T12:30:00",
    )
    assert writes == []
    assert first.read_bytes() == b"photo"
    assert second.read_bytes() == b"video"

    result = apply_multiple_metadata_correction(
        workspace_root=tmp_path,
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-07-21T12:30:00",
        expected_preview_fingerprint=preview["preview_fingerprint"],
    )

    assert result["status"] == "completed"
    assert result["file_count"] == 2
    assert writes == [
        ("A.JPG", "jpeg", "2026-07-21T12:30:00"),
        ("B.MP4", "video", "2026-07-21T12:35:30"),
    ]
    assert b"2026-07-21T12:30:00" in first.read_bytes()
    assert b"2026-07-21T12:35:30" in second.read_bytes()


def test_0340_changed_file_invalidates_preview(tmp_path: Path, monkeypatch):
    root = tmp_path / "Metadatenkorrektur" / "Mehrfachkorrektur"
    root.mkdir(parents=True)
    first = root / "A.JPG"
    second = root / "B.MP4"
    first.write_bytes(b"photo")
    second.write_bytes(b"video")
    monkeypatch.setattr(metadata_correction, "analyze_tree", _fake_multiple_analysis)

    preview = preview_multiple_metadata_correction(
        workspace_root=tmp_path,
        library_id="main",
        reference_relative_path="A.JPG",
        proposed_datetime="2026-07-21T12:30:00",
    )
    second.write_bytes(b"video-changed")

    with pytest.raises(MetadataCorrectionError, match="Vorschau"):
        apply_multiple_metadata_correction(
            workspace_root=tmp_path,
            library_id="main",
            reference_relative_path="A.JPG",
            proposed_datetime="2026-07-21T12:30:00",
            expected_preview_fingerprint=preview["preview_fingerprint"],
        )


def test_0340_multiple_scan_requires_no_database(tmp_path: Path, monkeypatch):
    root = tmp_path / "Metadatenkorrektur" / "Mehrfachkorrektur"
    root.mkdir(parents=True)
    (root / "A.JPG").write_bytes(b"photo")
    (root / "B.MP4").write_bytes(b"video")
    monkeypatch.setattr(metadata_correction, "analyze_tree", _fake_multiple_analysis)

    scan = scan_metadata_area(
        area="multiple",
        workspace_root=tmp_path,
        library_id="main",
    )
    assert scan["area"] == "multiple"
    assert scan["summary"]["file_count"] == 2
    assert scan["summary"]["usable_time_count"] == 2


def test_0340_ui_has_preview_apply_and_import_flow():
    assert "Vorschau berechnen" in METADATA_CORRECTION_HTML
    assert ">Anwenden<" in METADATA_CORRECTION_HTML
    assert "Anwenden und in Tagesbestand übernehmen" in METADATA_CORRECTION_HTML
    assert "/api/metadata-correction/multiple/preview" in METADATA_CORRECTION_HTML
    assert "/api/metadata-correction/multiple/apply" in METADATA_CORRECTION_HTML
    assert "Alt→Neu" not in METADATA_CORRECTION_HTML


def test_0340_worker_supports_managed_multiple_import():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert '"metadata_multiple_import"' in source
    assert "allow_workspace_source=managed_multiple_import" in source
    assert "imported_source_files" in source
    assert "Mehrfachkorrektur-Import verweist auf einen unerwarteten Quellordner." in source


def test_0340_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.35.5"
