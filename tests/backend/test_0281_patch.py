"""0.28.1 regressions from the first manual 0.28.0 deep test."""
from pathlib import Path

from app import main
from app.database import database_connection, initialize_database
from app.event_layout import (
    ensure_event_layout_snapshot,
    get_global_default,
    update_event_layout,
)
from tests.backend.test_0280_foundation import NOW, _event, _job


def test_0281_settings_api_persists_global_folder_layout(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    monkeypatch.setattr(main, "DATABASE_FILE", db)

    payload = {
        "structure_enabled": False,
        "input_path": "",
        "layout": {
            "version": 1,
            "nodes": [
                {"id": "all", "name": "All", "children": []},
                {"id": "fav", "name": "Favoriten", "children": []},
            ],
        },
    }
    saved = main.api_set_event_folder_layout(payload)

    assert saved["structure_enabled"] is False
    assert saved["input_path"] == ""
    with database_connection(db) as connection:
        stored = get_global_default(connection)
    assert stored == saved


def test_0281_stored_structure_preview_respects_event_folder_snapshot(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        _job(connection, "a")
        _event(connection)
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        update_event_layout(
            connection,
            "e",
            structure_enabled=False,
            input_path="Alle",
            layout={
                "version": 1,
                "nodes": [
                    {"id": "legacy-alle", "name": "Alle", "children": []},
                    {"id": "legacy-sortiert", "name": "Sortiert", "children": []},
                    {"id": "legacy-export", "name": "Export", "children": []},
                ],
            },
            updated_at=NOW,
        )

    monkeypatch.setattr(main, "DATABASE_FILE", db)
    monkeypatch.setattr(main, "refresh_live_event_inventories", lambda *args, **kwargs: None)

    data = main.api_event_structure("a", "e")

    assert "07-19 - Test" in data["structure_text"]
    assert "Alle" not in data["structure_text"]
    assert "Sortiert" not in data["structure_text"]
    assert "Export" not in data["structure_text"]
    assert data["event"]["folder_layout"]["structure_enabled"] is False


def test_0281_settings_ui_is_compact_and_updates_workspace_default_live():
    shell = Path("app/ui_shell.py").read_text(encoding="utf-8")
    workspace = Path("app/workspace_ui.py").read_text(encoding="utf-8")

    assert "bk-folder-layout-toggle" in shell
    assert "bk-folder-input-root" in shell
    assert "bk-folder-input-radio" in shell
    assert "await response.text()" in shell
    assert "bibliothekar:folder-layout-updated" in shell
    assert "bibliothekar:folder-layout-updated" in workspace
