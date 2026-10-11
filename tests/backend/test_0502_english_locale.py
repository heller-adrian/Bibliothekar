"""0.50.3 English-first UI and safe legacy storage defaults.

Tests only use disposable synthetic paths. No TrueNAS/production mounts.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import os

from app.event_naming import DEFAULT_NO_EVENT_LABEL, normalize_event_naming
from app.storage_config import load_storage_settings, storage_paths
from app.ui_i18n import UI_TRANSLATIONS, I18N_UI_JS
from app.security import _login_html
from app.main import _library_onboarding_html


def test_0502_localisation_is_english_first_and_reversible():
    assert len(UI_TRANSLATIONS) >= 400
    assert 'const key = "bibliothekar-language"' in I18N_UI_JS
    assert 'let locale = "en"' in I18N_UI_JS
    assert "MutationObserver" in I18N_UI_JS
    assert "data-bk-language-choice" in I18N_UI_JS
    assert 'new CustomEvent("bk-language-changed"' in I18N_UI_JS
    assert "const reverseDictionary" in I18N_UI_JS
    assert UI_TRANSLATIONS["Änderungsauftrag"] == "Change request"
    assert UI_TRANSLATIONS["Papierkorb"] == "Trash"
    assert UI_TRANSLATIONS["Ereignisordner extern gelöscht"] == "Event folder deleted externally"


def test_0502_localisation_javascript_parses(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        return
    js = tmp_path / "i18n.js"
    js.write_text(I18N_UI_JS, encoding="utf-8")
    subprocess.run([node, "--check", str(js)], check=True, capture_output=True)


def test_0502_english_defaults_and_no_unrequested_renames(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)

    english = load_storage_settings()
    assert english == {
        "backup_directory_name": "SD Card Backups",
        "workspaces_directory_name": "Library Workspaces",
        "metadata_directory_name": "Metadata Correction",
        "trash_directory_name": "Trash",
    }
    assert storage_paths(workspace)["backup_root"] == workspace / "SD Card Backups"
    assert list(workspace.iterdir()) == []

    # On an upgraded installation, existing physical roots win when no
    # explicit names are stored. No files are ever moved during language setup.
    for folder in ("SD-Kartensicherungen", "Arbeitsbereiche", "Metadatenkorrektur", "Papierkorb"):
        (workspace / folder).mkdir()
        (workspace / folder / "owner.txt").write_text("user", encoding="utf-8")
    german = load_storage_settings()
    assert german["backup_directory_name"] == "SD-Kartensicherungen"
    assert german["workspaces_directory_name"] == "Arbeitsbereiche"
    assert german["metadata_directory_name"] == "Metadatenkorrektur"
    assert german["trash_directory_name"] == "Papierkorb"
    assert all((workspace / folder / "owner.txt").read_text() == "user"
               for folder in ("SD-Kartensicherungen", "Arbeitsbereiche", "Metadatenkorrektur", "Papierkorb"))


def test_0502_naming_defaults_are_english_and_legacy_opt_in(monkeypatch):
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    assert DEFAULT_NO_EVENT_LABEL == "No Event"
    assert normalize_event_naming({})["no_event_label"] == "No Event"
    monkeypatch.setenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", "de")
    assert normalize_event_naming({})["no_event_label"] == "Ohne Ereignis"
    assert normalize_event_naming({"no_event_label": "Eigene Sammlung"})["no_event_label"] == "Eigene Sammlung"


def test_0502_login_setup_and_settings_get_localisation():
    login = _login_html(unavailable=True)
    assert '<html lang="en">' in login
    assert "Secure access to your camera library" in login
    assert "I18N_UI_JS" not in login
    assert "const dictionary = " in login
    onboarding = _library_onboarding_html()
    assert '<html lang="en">' in onboarding
    assert "const dictionary = " in onboarding

    from app.ui_shell import apply_shell
    html = apply_shell("<html><head><title>Page</title></head><body><main>Content</main></body></html>", active_area="import")
    assert 'data-bk-language-choice="en"' in html
    assert 'data-bk-language-choice="de"' in html
    assert "MutationObserver" in html
    assert 'data-bk-version>0.50.4</span>' in html


def test_0502_english_new_install_inventory_reconcile(tmp_path: Path, monkeypatch):
    from app.database import initialize_database, database_connection
    from app.workspace_layout import ensure_workspace_layout
    from app.central_stock_reconcile import reconcile_central_free_stock
    from tests.backend.test_0412_consistency_semantics import _seed_free_file

    workspace = tmp_path / "new-workspace"
    workspace.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path / "new-settings.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    db = tmp_path / "fresh.sqlite3"
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])
    assert central.name == "SD Card Backups"
    assert (workspace / "Library Workspaces").is_dir()
    assert (workspace / "Metadata Correction").is_dir()
    assert (workspace / "Trash").is_dir()

    _family, file_id, relative = _seed_free_file(
        db, family_key="ENGLISH", filename="ENGLISH.JPG",
        day="2026-10-10", data=b"english-first-original",
    )
    source = central / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"english-first-original")
    result = reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    assert result["ready"] is True
    assert result["deleted_file_count"] == 0
    assert result["misplaced_file_count"] == 0
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT 1 FROM files WHERE id=?", (file_id,)
        ).fetchone()
    assert source.read_bytes() == b"english-first-original"


def test_0502_new_english_no_event_folder(tmp_path: Path, monkeypatch):
    from app.event_naming import render_no_event_folder_name
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    assert render_no_event_folder_name("2026-10", {}) == "10 - No Event"
    assert render_no_event_folder_name(
        "2026-10", {"no_event_label": "My Unsorted Photos"}
    ) == "10 - My Unsorted Photos"
