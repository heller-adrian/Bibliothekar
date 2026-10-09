from __future__ import annotations

import errno
import os
from pathlib import Path

from app import main, safe_transfer, ui_shell
from app.metadata import build_candidates, select_candidate


def test_0323_exdev_after_same_device_hint_falls_back_to_verified_copy(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source" / "photo.JPG"
    destination = tmp_path / "target" / "photo.JPG"
    source.parent.mkdir()
    destination.parent.mkdir()
    payload = b"bibliothekar-exdev-fallback" * 128
    source.write_bytes(payload)

    monkeypatch.setattr(safe_transfer, "_same_filesystem", lambda *_: True)
    real_link = os.link
    calls = {"count": 0}

    def exdev_once(src, dst, *, follow_symlinks=True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real_link(src, dst, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(safe_transfer.os, "link", exdev_once)

    result = safe_transfer.move_verified_no_overwrite(
        source,
        destination,
        expected_size=len(payload),
        expected_sha256=safe_transfer.sha256_file(source),
    )

    assert result["method"] == "copy_verify_delete"
    assert calls["count"] >= 2
    assert not source.exists()
    assert destination.read_bytes() == payload


def test_0323_metadata_recognizes_exif_datetime_across_group1_paths():
    candidates = build_candidates(
        {
            "EXIF:SubIFD:DateTimeOriginal": "2026:07:25 12:34:56+03:00",
            "File:System:FileModifyDate": "2026:10:02 01:53:00+02:00",
        },
        "jpeg",
    )

    selected, source, confidence, conflict = select_candidate(candidates, "jpeg")

    assert selected == "2026-07-25T12:34:56+03:00"
    assert source == "EXIF:SubIFD:DateTimeOriginal"
    assert confidence == "high"
    assert conflict is False


def test_0323_metadata_recognizes_quicktime_movieheader_create_date():
    candidates = build_candidates(
        {
            "QuickTime:MovieHeader:CreateDate": "2026:07:25 12:35:10+03:00",
            "File:System:FileModifyDate": "2026:10:02 03:08:00+02:00",
        },
        "video",
    )

    selected, source, confidence, conflict = select_candidate(candidates, "video")

    assert selected == "2026-07-25T12:35:10+03:00"
    assert source == "QuickTime:MovieHeader:CreateDate"
    assert confidence == "high"
    assert conflict is False


def test_0323_shell_shows_current_library_and_old_review_route_is_removed():
    shell = ui_shell._shell_markup("workspace", "captures")

    assert 'id="bk-current-library-name"' in shell
    assert "Bibliothek …" not in shell
    assert "Hauptbibliothek" in shell
    assert "/api/libraries/current" in ui_shell.BIBLIOTHEKAR_JS
    assert "0.47.3 · Kamerakern 0.32.11" in shell
    assert main.DEPLOYMENT_VERSION == "0.47.3"
    assert "/review" not in {
        getattr(route, "path", None)
        for route in main.app.routes
    }
