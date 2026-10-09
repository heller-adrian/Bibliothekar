"""0.47.4: Quelle ohne Alt-Mount, echte Ordnerzahlen und eindeutige Anzeige."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import __version__, main
from app.database import initialize_database

ROOT = Path(__file__).resolve().parents[2]


def test_0474_version_and_dock_are_single_source_of_truth():
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    assert __version__ == main.DEPLOYMENT_VERSION == main.RELEASE_VERSION == "0.47.4"
    assert "Version <span data-bk-version>0.47.4</span>" in shell
    assert "Kamerakern 0.32.11" not in shell
    assert "· Kern ${core}" not in shell
    assert 'width:48px;' in shell
    assert 'height:48px;' in shell
    assert 'min-width:48px;' in shell
    assert 'min-height:48px;' in shell
    assert 'border-radius:14px;' in shell
    assert 'aria-label="Hintergrundvorgänge verkleinern"' in shell
    assert 'viewBox="0 0 24 24"' in shell
    assert 'title="Hinweis verkleinern">×' not in shell


def test_0474_legacy_source_picker_removed_but_import_kept():
    code = (ROOT / "app" / "main.py").read_text()
    compose = (ROOT / "compose.example.yaml").read_text()
    assert "Bereits erkannte Sicherungsquellen" not in code
    assert 'value="saved">Bisherige Sicherungsquellen' not in code
    assert 'id="source-select"' not in code
    assert 'id="import-button"' not in code
    assert 'id="folder-source-detail"' in code
    assert "updateFolderSourceDetail(currentFolderRoot, currentFolderPath)" in code
    assert "folderSummaryRequest" in code
    assert "sourceSelect" not in code
    assert "loadSources(" not in code
    assert '"/api/jobs/folder-import"' in code
    assert '"/api/source-folder-summary"' in code
    assert 'device.device_id, device.label || device.model || "SD-Karte"' in code
    assert "/sources/import" not in compose
    assert "/sources/nas:ro" in compose


def test_0474_statistics_follow_selected_nas_folder(tmp_path, monkeypatch):
    db = tmp_path / "library.sqlite3"
    initialize_database(db)
    nas = tmp_path / "nas"
    one = nas / "2025" / "Neuseeland"
    two = nas / "2025" / "Andere Reise"
    (one / "DCIM").mkdir(parents=True)
    two.mkdir(parents=True)
    (one / "DCIM" / "foo.jpg").write_bytes(b"JPEG-1")
    (one / "DCIM" / "foo.raf").write_bytes(b"RAF-2")
    (one / "NOTES.TXT").write_bytes(b"memo")
    (two / "bar.jpg").write_bytes(b"another")
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", nas)

    data = main.api_source_folder_summary("nas", "2025/Neuseeland")
    assert data["relative_path"] == "2025/Neuseeland"
    assert data["file_count"] == 3
    assert data["media_file_count"] == 2
    assert data["total_size_bytes"] == len(b"JPEG-1RAF-2memo")
    assert main.api_source_folder_summary("nas", "2025/Andere Reise")["file_count"] == 1

    with pytest.raises(HTTPException) as traversal:
        main.api_source_folder_summary("nas", "../")
    assert traversal.value.status_code == 422
    with pytest.raises(HTTPException) as root:
        main.api_source_folder_summary("nas", ".")
    assert root.value.status_code == 422


def test_0474_removable_card_needs_no_saved_source_mount(tmp_path, monkeypatch):
    db = tmp_path / "library.sqlite3"
    initialize_database(db)
    mount = tmp_path / "removable"
    card = mount / "CARD01"
    (card / "DCIM").mkdir(parents=True)
    (card / "DCIM" / "img.mov").write_bytes(b"video")
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    monkeypatch.setattr(main, "REMOVABLE_ROOT", mount)
    monkeypatch.setattr(main, "IMPORT_ROOT", tmp_path / "missing-saved-mount")
    stats = main.api_source_folder_summary("removable", "CARD01")
    assert stats["media_file_count"] == 1
    assert stats["source_device_id"] == "CARD01"
