"""0.54.2 regression: screenshot copy, non-destructive defaults and immediate loading feedback."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import pytest

from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS, I18N_UI_JS
from app.event_layout import DEFAULT_LAYOUT, DEFAULT_SETTING, ENGLISH_NEW_INSTALL_SETTING, get_global_default, set_global_default
from app.database import initialize_database, database_connection
from app.ui_shell import apply_shell, BIBLIOTHEKAR_JS, BIBLIOTHEKAR_0505_LANGUAGE_CSS
from app.workspace_ui import WORKSPACE_HTML

SCREENSHOTS = {
    "Zielstruktur-Vorschau": "Destination structure preview",
    "Arbeitsbestand": "Workspace inventory",
    "Auswahlzeitraum": "Selection period",
    "Ereignis bearbeiten": "Edit event",
    "Änderungen anwenden": "Apply changes",
    "Zielgruppen": "Destination groups",
    "Datenmenge": "Data size",
    "Notizen": "Notes",
    "Unterordner": "Subfolders",
    "Sicherheitsstatus": "Security status",
    "Hinweise": "Notes",
    "Geplante Ziele": "Planned destinations",
    "Familien anzeigen": "Show families",
    "Sortierung anwenden": "Apply sorting",
    "Sortierung jetzt anwenden": "Apply sorting now",
    "Unterereignis entfernen": "Remove subevent",
    "Der gewählte Zeitraum ist ungültig.": "The selected date range is invalid.",
    "Keine Zielstruktur vorhanden.": "No destination structure available.",
    "Rückänderung vorbereiten": "Prepare reversal",
    "Manuelle Ereignisänderung": "Manual event change",
}

def test_0506_screenshot_strings_are_in_global_translation_catalog():
    for src, expected in SCREENSHOTS.items():
        assert UI_TRANSLATIONS[src] == expected
    assert len(UI_PATTERNS) > 75

def test_0506_nav_shows_feedback_without_network_gate():
    rendered = apply_shell(
        "<html><head></head><body><main>German first paint</main></body></html>",
        active_area="workspace",
    )
    assert 'root.dataset.bkNavLoading = "true"' in BIBLIOTHEKAR_JS
    assert 'requestAnimationFrame(() => requestAnimationFrame(() => window.location.assign(href)))' in BIBLIOTHEKAR_JS
    assert 'window.setTimeout(() => window.location.assign(href), 190)' not in BIBLIOTHEKAR_JS
    assert 'html[data-bk-display-mode="standalone"][data-bk-i18n-pending="true"]::before' in rendered
    assert 'html[data-bk-display-mode="standalone"][data-bk-nav-loading="true"]::after' in BIBLIOTHEKAR_0505_LANGUAGE_CSS
    assert 'data-bk-version>0.54.2</span>' in rendered

def test_0506_workspace_long_labels_fit_and_preview_dates_wrap():
    assert '.summary > .card > .muted' in WORKSPACE_HTML
    assert 'font-size:clamp(.63rem, .84vw, .85rem)' in WORKSPACE_HTML
    assert '.preview-selection-note .preview-period-dates' in WORKSPACE_HTML
    assert 'white-space:normal!important' in WORKSPACE_HTML
    assert 'Selection period:' in WORKSPACE_HTML
    assert 'Destination structure preview' in WORKSPACE_HTML

def test_0506_english_default_is_explicitly_provisioned_and_legacy_is_stable(tmp_path: Path):
    # Keep the historical API fallback and event snapshots unchanged.
    assert [x["name"] for x in DEFAULT_LAYOUT["nodes"]] == ["Alle", "Sortiert", "Export"]
    assert DEFAULT_SETTING["input_path"] == "Alle"
    assert [x["name"] for x in ENGLISH_NEW_INSTALL_SETTING["layout"]["nodes"]] == ["All", "Sorted", "Export"]
    assert ENGLISH_NEW_INSTALL_SETTING["input_path"] == "All"
    db = tmp_path / "fresh.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        set_global_default(connection, ENGLISH_NEW_INSTALL_SETTING, updated_at="2026-10-11T00:00:00Z")
        result = get_global_default(connection)
        assert result["input_path"] == "All"
        assert [x["name"] for x in result["layout"]["nodes"]] == ["All", "Sorted", "Export"]
    # Reopen: saved choice is retained, without any directory changes.
    with database_connection(db) as connection:
        assert get_global_default(connection)["input_path"] == "All"
    assert not (tmp_path / "Alle").exists()
    assert not (tmp_path / "All").exists()

def test_0506_generated_preformatted_error_translation_without_path_renames(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    harness = r"""
globalThis.localStorage = {getItem: () => "en", setItem: () => {}};
globalThis.document = {
  title: "Sortieren", readyState: "loading",
  documentElement: {dataset: {}, lang: ""},
  addEventListener: () => {}, querySelectorAll: () => [], body: null
};
globalThis.window = {
  alert: () => {}, confirm: () => false, prompt: () => null,
  dispatchEvent: () => {}
};
globalThis.CustomEvent = function() {};
eval(SCRIPT);
const i18n = window.BibliothekarI18n;
function eq(actual, expected) {if(actual !== expected)throw Error(JSON.stringify({actual, expected}));}
eq(i18n.t("Ereignis bearbeiten · Test eng"), "Edit event · Test eng");
eq(i18n.t("Änderungen anwenden · Test eng 2"), "Apply changes · Test eng 2");
eq(i18n.previewText("Der gewählte Zeitraum ist ungültig."), "The selected date range is invalid.");
eq(i18n.previewText("Zeitraum:\n2026-07-24 00:00\nbis 2026-07-24 23:59\nAuswahl: 16 Dateien, 8 Familien"),
   "Period:\n2026-07-24 00:00\nto 2026-07-24 23:59\nSelection: 16 files, 8 families");
eq(i18n.previewText("2026\n└── 07-24 - Test eng\n    ├── Alle\n    ├── Sortiert"),
   "2026\n└── 07-24 - Test eng\n    ├── Alle\n    ├── Sortiert");
i18n.setLocale("de");
eq(i18n.previewText("Der gewählte Zeitraum ist ungültig."), "Der gewählte Zeitraum ist ungültig.");
console.log("PASS");
"""
    js = tmp_path / "0506-ui.cjs"
    js.write_text("const SCRIPT = " + json.dumps(I18N_UI_JS, ensure_ascii=False) + ";\n" + harness, encoding="utf-8")
    result = subprocess.run([node, str(js)], capture_output=True, text=True, check=True)
    assert "PASS" in result.stdout
