from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app import main
import app.metadata_correction as metadata_correction
from app.metadata_correction_ui import METADATA_CORRECTION_HTML


def test_0336_metadata_card_stays_inside_parent_and_click_adds_selection():
    assert "box-sizing:border-box" in METADATA_CORRECTION_HTML
    assert "state.selectedSet.add(index);" in METADATA_CORRECTION_HTML
    assert "else if(state.selectedSet.size===0)" not in METADATA_CORRECTION_HTML


def test_0336_still_write_normalizes_exif_and_xmp(monkeypatch, tmp_path: Path):
    path = tmp_path / "test.JPG"
    path.write_bytes(b"jpeg")
    captured: list[list[str]] = []

    def fake_run(command, check=False, capture_output=True, text=True):
        captured.append(list(command))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(metadata_correction.subprocess, "run", fake_run)

    metadata_correction.write_metadata_datetime(
        path,
        "jpeg",
        "2026-10-03T21:14:58",
    )

    command = captured[0]
    assert "-EXIF:DateTimeOriginal=2026:10:03 21:14:58" in command
    assert "-EXIF:CreateDate=2026:10:03 21:14:58" in command
    assert "-XMP-exif:DateTimeOriginal=2026:10:03 21:14:58" in command
    assert "-XMP-xmp:CreateDate=2026:10:03 21:14:58" in command
    assert "-XMP-xmp:ModifyDate=2026:10:03 21:14:58" in command


def test_0336_reintegration_code_never_accepts_ohne_datum_destination():
    source = Path("app/metadata_correction.py").read_text(encoding="utf-8")
    assert "Korrigierte Metadaten würden erneut in Ohne_Datum einsortiert." in source
    assert 'record["selected_capture_time"] = proposed[:19]' in source
    assert 'record["capture_time_confidence"] = "high"' in source


def test_0336_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.41.3"
