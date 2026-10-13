"""0.47.3: Speicher-Vorprüfung und sicherer, jobspezifischer Importabbruch."""
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import __version__, main
from app.folder_import import (
    ImportCancelled, PipelineError, preflight_folder_import,
    move_import_into_workspace,
)
from app.pipeline import copy_and_verify, source_manifest
from app.ui_shell import BIBLIOTHEKAR_0455_CSS, apply_shell


def test_0455_version_and_phase_css():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.55.2"
    html = apply_shell("<html><head></head><body></body></html>", active_area="import")
    assert "Version <span data-bk-version>0.55.2</span>" in html
    assert f"<style>{BIBLIOTHEKAR_0455_CSS}</style>" in html
    assert "--bk-ink) 2%)" in BIBLIOTHEKAR_0455_CSS


def test_0455_preflight_rejects_quota_before_hash(tmp_path, monkeypatch):
    source, workspace = tmp_path / "source", tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    (source / "large.jpg").write_bytes(b"x" * 300)
    monkeypatch.setattr(
        "app.folder_import.os.statvfs",
        lambda _: SimpleNamespace(f_bavail=100, f_frsize=1)
    )
    with pytest.raises(PipelineError, match="Nicht genügend freier Speicher"):
        preflight_folder_import(
            source, workspace, workspace,
            processing_buffer_percent=10, safety_reserve_gib=0
        )


def test_0455_preflight_bounded_and_source_unchanged(tmp_path):
    source, workspace = tmp_path / "source", tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    for i in range(4):
        (source / f"{i}.jpg").write_text(f"photo{i}")
    with pytest.raises(PipelineError, match="zu viele Einträge"):
        preflight_folder_import(
            source, workspace, workspace, processing_buffer_percent=0,
            safety_reserve_gib=0, max_entries=2
        )
    assert len(list(source.iterdir())) == 4


def test_0455_copy_cancels_within_large_single_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    data = b"0" * (5 * 1024 * 1024)
    (source / "large.raf").write_bytes(data)
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise ImportCancelled("stop")
    entry = {"relative_path": "large.raf", "size_bytes": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}
    with pytest.raises(ImportCancelled, match="stop"):
        copy_and_verify(source, target, [entry], cancellation_callback=cancel)
    assert (source / "large.raf").read_bytes() == data
    assert (target / "large.raf").stat().st_size < len(data)


def test_0455_hash_cancels_inside_one_large_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "large.raf").write_bytes(b"x" * (6 * 1024 * 1024))
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise ImportCancelled("stop")
    with pytest.raises(ImportCancelled):
        source_manifest(source, cancellation_callback=cancel)
    assert (source / "large.raf").stat().st_size == 6 * 1024 * 1024


def test_0455_move_never_removes_foreign_destination(tmp_path):
    source = tmp_path / "temporary"
    dest = tmp_path / "central"
    source.mkdir()
    dest.mkdir()
    (source / "a.jpg").write_bytes(b"new")
    (dest / "a.jpg").write_bytes(b"foreign")
    plan = [{"source_relative_path": "a.jpg", "destination_relative_path": "a.jpg",
             "size_bytes": 3, "sha256": hashlib.sha256(b"new").hexdigest()}]
    with pytest.raises(PipelineError, match="existiert bereits"):
        move_import_into_workspace(source, dest, plan)
    assert (dest / "a.jpg").read_bytes() == b"foreign"
    assert (source / "a.jpg").read_bytes() == b"new"


def test_0455_cancel_request_is_persistent_and_job_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "LOG_PATH", tmp_path)
    main._request_import_cancel("job_a")
    assert main._import_cancel_requested("job_a")
    assert not main._import_cancel_requested("job_b")
    with main.IMPORT_CANCEL_LOCK:
        main.IMPORT_CANCEL_REQUESTS.clear()
    assert main._import_cancel_requested("job_a")
    assert main._import_cancel_info("job_a")["cancel_requested"]
    main._request_import_cancel("job_a", force=True)
    assert main._import_cancel_info("job_a")["cancel_forced"]
    main._clear_import_cancel("job_a")
    assert not main._import_cancel_requested("job_a")


def test_0455_force_requires_existing_request_and_grace(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "LOG_PATH", tmp_path)
    monkeypatch.setattr(main, "get_job", lambda *args: {
        "id": "job_c", "kind": "sd_import",
        "operation": "folder_import", "state": "copying"
    })
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match=""):
        main.api_cancel_import("job_c", force=True)
    main.api_cancel_import("job_c")
    with pytest.raises(HTTPException):
        main.api_cancel_import("job_c", force=True)
    marker = main._import_cancel_marker("job_c")
    old = marker.stat().st_mtime - 20
    os.utime(marker, (old, old))
    result = main.api_cancel_import("job_c", force=True)
    assert result.status_code == 202
    assert main._import_cancel_info("job_c")["cancel_forced"]
    main._clear_import_cancel("job_c")


def test_0455_history_uses_real_phase_values():
    from pathlib import Path
    code = (Path(__file__).resolve().parents[2] / "app/main.py").read_text()
    assert 'item["stage_progress_current"] = int(details.get("progress_current") or 0)' in code
    assert 'item["stage_progress_total"] = int(details.get("progress_total") or 0)' in code
    assert "bk-stage-badge" in code
    assert "requestForcedImportCancel" in code
    assert "preflight_folder_import(" in code
    assert "for item in committed_plan:" in (
        Path(__file__).resolve().parents[2] / "app/folder_import.py"
    ).read_text()
