"""0.55.0 regression: physical staging paths and non-destructive localization."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import __version__
from app import archive_change_assistant as assistant
from app.archive_staging import staging_directory_name
from app.managed_directory_names import AmbiguousManagedDirectoryError


@pytest.mark.parametrize("physical_name", ["Assign Later", "Später zuordnen"])
def test_archive_document_instruction_uses_actual_staging_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, physical_name: str
) -> None:
    workspace = tmp_path / "workspace"
    work_root = workspace / "Library Workspaces" / "test-library"
    archive = tmp_path / "archive"
    archive.mkdir()
    (work_root / physical_name).mkdir(parents=True)

    request = {
        "event_id": "ev-test",
        "event_name": "Historic event",
        "status": "aenderbar_bestaetigt",
        "delete_event": 0,
        "prepared_structure_path": physical_name + "/2026/Event",
    }
    description = {
        "required": True,
        "target_root": "2026/Event",
        "current_root": "2026/Event",
        "missing_directories": [],
        "helper_directories": [],
        "desired_directories": [],
        "obsolete_directories": [],
        "event_document": {
            "target_relative_path": "2026/Event/event.json",
            "size_bytes": 4,
            "sha256": "a" * 64,
        },
    }
    monkeypatch.setattr(assistant, "get_event_change_request", lambda *_: request)
    monkeypatch.setattr(assistant, "get_event_change_files", lambda *_: [])
    monkeypatch.setattr(assistant, "describe_archive_change_staging_for_request", lambda *_: description)
    monkeypatch.setattr(assistant, "describe_archive_release_stock", lambda *_: {"required": False})
    monkeypatch.setattr(assistant, "shared_work_root", lambda *_: work_root)

    outcome = assistant.build_archive_change_assistant(
        tmp_path / "unused.sqlite3", archive, workspace, "cr-test"
    )
    source = next(op["source"] for op in outcome["operations"]
                  if op["kind"] == "replace_event_document")
    assert source == "Arbeitsbereich/" + physical_name + "/2026/Event/event.json"
    assert outcome["preparation"]["staging_root"] == "Arbeitsbereich/" + physical_name
    assert outcome["path_labels"]["staging_root"] == "Arbeitsbereich/" + physical_name


def test_new_workspaces_resolve_english_but_legacy_names_survive(tmp_path: Path) -> None:
    work_root = tmp_path / "Library Workspaces" / "fresh"
    work_root.mkdir(parents=True)
    assert staging_directory_name(work_root) == "Assign Later"
    (work_root / "Später zuordnen").mkdir()
    assert staging_directory_name(work_root) == "Später zuordnen"


def test_conflicting_nonempty_legacy_and_english_staging_blocked(tmp_path: Path) -> None:
    for name in ("Später zuordnen", "Assign Later"):
        path = tmp_path / name
        path.mkdir()
        (path / "original.txt").write_text(name)
    with pytest.raises(AmbiguousManagedDirectoryError):
        staging_directory_name(tmp_path)


def test_explicit_dynamic_label_contract_and_raw_logs() -> None:
    repo = Path(__file__).resolve().parents[2]
    main = (repo / "app" / "main.py").read_text()
    events = (repo / "app" / "events_ui.py").read_text()
    workspace = (repo / "app" / "workspace_ui.py").read_text()
    archive = (repo / "app" / "archive_change_assistant.py").read_text()
    assert __version__ == "0.55.4"
    assert "STAGING_DIRECTORY_NAME" not in archive
    assert "staging_directory_name(work_root)" in archive
    assert 'bk0511EventLabel("IST","Actual")' in events
    assert 'bk0511EventLabel("SOLL","To Be")' in events
    assert 'bk0511OperationTitle(operation)' in events
    assert "bk0511PreviewLabel" in workspace
    assert "bk0511ImportLabel" in main
    assert "return job;" in main[main.index("function localizedTechnicalJob(job)"):][:100]
    assert "JSON.stringify(" in main
