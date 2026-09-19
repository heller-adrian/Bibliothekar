from pathlib import Path

from app import main
from app.pipeline import copy_and_verify, source_manifest


def test_0220_version_and_app_shell():
    assert main.APP_VERSION == "0.22.0"

    html = main.index()
    assert "Bibliothekar" in html
    assert "Import &amp; Prüfung" in html
    assert "Arbeitsbereich" in html
    assert "Archiv" in html
    assert "Bibliothek wechseln" in html
    assert "Einstellungen" in html
    assert "Bibliothekar Assistent" in html
    assert 'data-bk-theme-choice="light"' in html
    assert 'data-bk-theme-choice="dark"' in html
    assert 'data-bk-theme-choice="system"' in html


def test_0220_workspace_groups_captures_and_events():
    captures = main.workspace_interface().body.decode("utf-8")
    events = main.events_interface().body.decode("utf-8")

    assert 'class="bk-workspace-subnav"' in captures
    assert '>Aufnahmen</a>' in captures
    assert '>Ereignisse</a>' in captures
    assert 'href="/workspace" class="active"' in captures

    assert 'class="bk-workspace-subnav"' in events
    assert 'href="/events" class="active"' in events


def test_0220_import_source_picker_keeps_all_paths():
    html = main.index()
    assert 'data-source-mode="sd"' in html
    assert 'data-source-mode="drive"' in html
    assert 'data-source-mode="folder"' in html
    assert 'id="device-select"' in html
    assert 'id="folder-root-select"' in html
    assert 'id="source-select"' in html


def test_0220_manifest_and_copy_report_live_progress(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "A.JPG").write_bytes(b"A" * 32)
    (source / "B.JPG").write_bytes(b"B" * 64)

    manifest_progress = []
    entries = source_manifest(
        source,
        progress_callback=lambda current, total: manifest_progress.append(
            (current, total)
        ),
    )
    assert manifest_progress == [(1, 2), (2, 2)]

    copy_progress = []
    destination = tmp_path / "destination"
    copy_and_verify(
        source,
        destination,
        entries,
        progress_callback=lambda phase, current, total: copy_progress.append(
            (phase, current, total)
        ),
    )

    assert ("copy", 1, 2) in copy_progress
    assert ("copy", 2, 2) in copy_progress
    assert ("verify", 1, 2) in copy_progress
    assert ("verify", 2, 2) in copy_progress
