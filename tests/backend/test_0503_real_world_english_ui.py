"""0.50.3: regression fixtures based on real iPhone/PWA screenshots.

Purely synthetic browser and storage data; no production paths are accessed.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from app.ui_i18n import UI_TRANSLATIONS, I18N_UI_JS


SCREEN_LABELS = {
    "Anwendung": "Application",
    "Bereit": "Ready",
    "Verbunden": "Connected",
    "Beschreibbar": "Writable",
    "Quelle sichern": "Back up source",
    "Hilfe zur Quellenwahl": "Help with choosing a source",
    "SD-Karte": "SD card",
    "SD-Karte einbinden": "Mount SD card",
    "SD-Karte sichern": "Back up SD card",
    "Sicherungsfilter": "Backup filter",
    "Tage": "Days",
    "Neuladen": "Reload",
    "Unterereignis:": "Subevent:",
    "Erstellt:": "Created:",
    "Archivverlauf": "Archive history",
    "Metadatenkorrektion": "Metadata correction",
    "Ohne-Datum-Bestand": "Undated inventory",
    "Keine Ohne-Datum-Familien vorhanden.": "No undated families found.",
    "Ordnerimport": "Folder Import",
    "Laufwerksimport": "Drive Import",
}


def test_0503_screenshot_english_labels_present():
    for source, expected in SCREEN_LABELS.items():
        assert UI_TRANSLATIONS[source] == expected, (source, expected)


def test_0503_dynamic_ui_labels_and_document_title(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    js = r'''
globalThis.localStorage = {getItem: () => null, setItem: () => {}};
globalThis.document = {
  title: "Metadatenkorrektion",
  readyState: "loading",
  documentElement: {dataset: {}, lang: ""},
  addEventListener: () => {},
  querySelectorAll: () => [],
  body: null,
};
globalThis.window = {
  alert: () => {},
  confirm: () => false,
  prompt: () => null,
  dispatchEvent: () => {},
};
globalThis.CustomEvent = function () {};
eval(I18N_SCRIPT);
const i18n = window.BibliothekarI18n;
if (i18n.getLocale() !== "en") throw Error("English must be the default");
if (document.title !== "Metadata correction") throw Error("Page title was not translated");
const cases = [
  ["Zuletzt aktualisiert: 11:48:37 PM", "Last updated: 11:48:37 PM"],
  ["Quelle: /workspace/SD-Kartensicherungen/Ohne_Datum", "Source: /workspace/SD-Kartensicherungen/Ohne_Datum"],
  ["Unterereignis: Teil B", "Subevent: Teil B"],
  ["Erstellt: 09.10.2026, 19:17", "Created: 09.10.2026, 19:17"],
  ["Status: angewendet", "Status: applied"],
  ["16 Familien · 32 Dateien", "16 families · 32 files"],
  ["32 Dateien 16 Familien", "32 files   16 families"],
  ["6 Tage", "6 days"],
  ["Ordnerimport · NAS_01", "Folder Import · NAS_01"],
  ["SD-Kartenimport · CARD_001", "SD Card Import · CARD_001"],
  ["SD-Karte · MassStorageClass · 29.7 GiB · VFAT · Bereit zum Einbinden",
   "SD card · MassStorageClass · 29.7 GiB · VFAT · Ready to mount"],
  ["2 Einträge ausgewählt.", "2 entries selected."],
  ["Die Vorschau zeigt nur die Planung.\n Es werden noch keine Ordner verändert.",
   "The preview only shows the plan. No folders have been changed."],
  ["Metadatenquelle übernehmen (2)", "Use metadata source (2)"],
];
for (const [raw, expected] of cases) {
  const actual = i18n.t(raw);
  if (actual !== expected) throw Error(JSON.stringify({raw, actual, expected}));
}
i18n.setLocale("de");
if (document.title !== "Metadatenkorrektion") throw Error("German document title not restored");
console.log("PASS " + cases.length);
'''
    test_file = tmp_path / "ui-0503.cjs"
    test_file.write_text(
        "const I18N_SCRIPT = " + json.dumps(I18N_UI_JS, ensure_ascii=False) + ";\n" + js,
        encoding="utf-8",
    )
    result = subprocess.run([node, str(test_file)], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "PASS 14"


def test_0503_english_roots_only_for_fresh_workspace(tmp_path: Path, monkeypatch):
    from app.storage_config import load_storage_settings, storage_paths
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("KAMERA_WORKSPACE", str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    names = load_storage_settings()
    assert names == {
        "backup_directory_name": "SD Card Backups",
        "workspaces_directory_name": "Library Workspaces",
        "metadata_directory_name": "Metadata Correction",
        "trash_directory_name": "Trash",
    }
    assert storage_paths(workspace)["backup_root"] == workspace / "SD Card Backups"
    # Rendering/setting language is never a file-system operation.
    assert list(workspace.iterdir()) == []
    (workspace / "SD-Kartensicherungen").mkdir()
    (workspace / "SD-Kartensicherungen" / "old.txt").write_text("untouched")
    assert load_storage_settings()["backup_directory_name"] == "SD-Kartensicherungen"
    assert (workspace / "SD-Kartensicherungen" / "old.txt").read_text() == "untouched"
