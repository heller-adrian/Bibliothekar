"""0.50.7 – desktop navigation, stored paths and import history English copy."""
from __future__ import annotations
from pathlib import Path
import json

from app.ui_shell import BIBLIOTHEKAR_JS, BIBLIOTHEKAR_0505_LANGUAGE_CSS
from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS
from app.storage_config import load_storage_settings, ENGLISH_STORAGE_DEFAULTS
from app.workspace_layout import ensure_workspace_layout
from app import main

def test_0507_desktop_navigation_does_not_block_header_or_disrupt_animation():
    s = BIBLIOTHEKAR_JS
    assert 'const pwa = root.dataset.bkDisplayMode === "standalone";' in s
    assert 'if (pwa) root.dataset.bkNavLoading = "true";' in s
    assert 'tab.classList.add("is-navigating", "bk-tab-pressing");' in s
    assert 'window.location.assign(href);' in s
    assert 'requestAnimationFrame(() => requestAnimationFrame(() => window.location.assign(href)));' in s
    css = BIBLIOTHEKAR_0505_LANGUAGE_CSS
    assert 'html[data-bk-display-mode="standalone"][data-bk-i18n-pending="true"] body' in css
    assert 'html[data-bk-display-mode="standalone"][data-bk-nav-loading="true"]::before' in css
    assert 'html[data-bk-nav-loading="true"]::before' not in css
    assert 'html[data-bk-i18n-pending="true"] body { visibility: hidden !important; }' not in css

def test_0507_import_messages_and_schema_are_in_catalog():
    messages = {
        "Ereignissortierung vollständig angewendet und geprüft.": "Event sorting fully applied and verified.",
        "Quelle wird vollständig in die temporäre Sicherung kopiert.": "Copying the entire source to a temporary backup.",
        "Temporäre Sicherung wird Datei für Datei per SHA-256 geprüft.": "Verifying the temporary backup file by file using SHA-256.",
        "Zentraler Aufnahmebestand wurde vollständig gegen das Manifest geprüft.": "Central photo inventory fully verified against the manifest.",
        "Restzeit": "Time remaining",
        "Fortschritt gesamt": "Overall progress",
        "Auftragsart": "Job type",
    }
    for source, target in messages.items():
        assert UI_TRANSLATIONS[source] == target
    assert main.RELEASE_VERSION in {"0.50.7", "0.54.1"}
    assert main.DEPLOYMENT_VERSION in {"0.50.7", "0.54.1"}
    # Database detail and import history are formatted by the app before rendering.
    assert 'Schema version ' in main.index()
    assert 'importUiText(job.progress_message || "Kein Statustext vorhanden.")' in main.index()
    assert 'Technical ID: ' in main.index()
    assert 'Job type: ' in main.index()

def test_0507_fresh_top_level_workspace_folders_are_english(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path / "new-settings.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    settings = load_storage_settings()
    assert settings == ENGLISH_STORAGE_DEFAULTS
    result = ensure_workspace_layout(workspace, create_default_main=False)
    for dirname in ("SD Card Backups", "Library Workspaces", "Metadata Correction", "Trash"):
        assert (workspace / dirname).is_dir(), dirname
    for dirname in ("SD-Kartensicherungen", "Arbeitsbereiche", "Metadatenkorrektur", "Papierkorb"):
        assert not (workspace / dirname).exists(), dirname

def test_0507_existing_root_names_are_never_silently_renamed(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    legacy = workspace / "SD-Kartensicherungen"
    legacy.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path / "existing.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    settings = load_storage_settings()
    assert settings["backup_directory_name"] == "SD-Kartensicherungen"
    assert settings["workspaces_directory_name"] == "Library Workspaces"
    assert legacy.is_dir()

def test_0507_technical_detail_retains_raw_evidence():
    html = main.index()
    assert "function localizedTechnicalJob(job)" in html
    assert "function importUiText(value)" in html
    assert "return job;" in html[html.index("function localizedTechnicalJob(job)"):][:100]
    assert "JSON.stringify(\n                  localizedTechnicalJob(job)" in html
    assert "JSON.stringify(" in html
    assert 'const englishExample=document.documentElement.dataset.bkLocale !== "de";' in __import__("app.ui_shell", fromlist=["BIBLIOTHEKAR_JS"]).BIBLIOTHEKAR_JS
