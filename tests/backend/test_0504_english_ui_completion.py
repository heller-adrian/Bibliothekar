"""0.50.4 real-screen English UI acceptance and safe German fallback.

No production files, NAS data or browser sessions are used.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from app.ui_i18n import UI_TRANSLATIONS, UI_PATTERNS, I18N_UI_JS
from app.ui_i18n_0504 import UI_0504_TRANSLATIONS, UI_0504_PATTERNS
from app.events_ui import EVENTS_HTML


SCREENSHOT_CASES = [
    ("Ausblenden", "Hide"),
    ("Ausgeblendet (0)", "Hidden (0)"),
    ("SD Card Import · Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01",
     "SD Card Import · Multiple cameras - 2026.07.19 - 2026.10.01"),
    ("Abgeschlossen · 108 Dateien", "Completed · 108 files"),
    ("Gespeicherte Ereignisse", "Saved events"),
    ("Angezeigte Ereignisse", "Displayed events"),
    ("Zugeordnete Familien", "Assigned families"),
    ("Löschbare Planungen", "Deletable plans"),
    ("3 von 3 Ereignissen · zuletzt geändert", "3 of 3 events · most recently changed"),
    ("2026-07-22T00:00 bis 2026-07-23T23:59 · 16 Familien",
     "2026-07-22T00:00 to 2026-07-23T23:59 · 16 families"),
    ("archiviert", "archived"),
    ("Startzeit", "Start time"),
    ("Endzeit", "End time"),
    ("Unterereignisse (optional)", "Subevents (optional)"),
    ("Tagesordner innerhalb des Ereignisses behalten", "Keep day folders within the event"),
    ("Vorschau einblenden", "Show preview"),
    ("Ereignis speichern", "Save event"),
    ("Papierkorb entleeren", "Empty trash"),
    ("Physischer Bestand geprüft · 0 bekannte Dateien · 99 nicht katalogisierte Dateien",
     "Physical inventory checked · 0 known files · 99 uncatalogued files"),
    ("99 Dateien · 1 Ordner", "99 files · 1 folder"),
    ("1 Ordner", "1 folder"),
    ("Inhalt des Papierkorbs", "Trash contents"),
    ("1 geplantes Ereignis", "1 planned event"),
    ("8 Familien · 16 Dateien. Standardmäßig werden alle unabhängigen geplanten Ereignisse angewendet.",
     "8 families · 16 files. By default, all independent planned events will be applied."),
    ("Auswahl anpassen", "Adjust selection"),
    ("Archivierte Sicherungen einblenden", "Show archived backups"),
    ("Benutzer 568:568", "User 568:568"),
    ("64 MiB frei", "64 MiB free"),
    ("Weitere anzeigen (4)", "Show more (4)"),
    ("Quelle: /workspace/Papierkorb", "Source: /workspace/Papierkorb"),
]

PROTECTED_VALUES = [
    "Test löschen",
    "Test eng",
    "07-22 - Test löschen",
    "/workspace/Papierkorb",
    "/workspace/SD-Kartensicherungen/Ohne_Datum",
    "Sommerurlaub",
    "IMG_5888.JPG",
]


def test_0504_all_screenshot_literals_and_dynamic_patterns():
    assert len(UI_0504_TRANSLATIONS) >= 150
    assert len(UI_0504_PATTERNS) >= 50
    assert UI_TRANSLATIONS["Löschbare Planungen"] == "Deletable plans"
    assert UI_PATTERNS[:len(UI_0504_PATTERNS)] == UI_0504_PATTERNS
    assert 'class="event-name" data-bk-preserve-language' in EVENTS_HTML
    assert 'class="event-folder" data-bk-preserve-language' in EVENTS_HTML


def test_0504_real_screen_dynamic_translation_and_locale_switch(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    javascript = r'''
globalThis.localStorage = {getItem: () => null, setItem: () => {}};
globalThis.document = {
  title: "Gespeicherte Ereignisse",
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
if (i18n.getLocale() !== "en") throw Error("Expected English locale by default");
if (document.title !== "Saved events") throw Error("Document title did not translate");
for (const [source, expected] of CASES) {
  const got = i18n.t(source);
  if (got !== expected) throw Error(JSON.stringify({source, got, expected}));
}
for (const original of PROTECTED) {
  if (i18n.t(original) !== original) throw Error("User data was translated: " + original);
}
i18n.setLocale("de");
if (document.title !== "Gespeicherte Ereignisse") throw Error("Document title did not restore");
if (i18n.getLocale() !== "de") throw Error("German locale was not selected");
i18n.setLocale("en");
if (document.title !== "Saved events") throw Error("Document title did not switch back");
console.log("PASS " + CASES.length + " cases and " + PROTECTED.length + " untouched values");
'''
    program = (
        "const I18N_SCRIPT = " + json.dumps(I18N_UI_JS, ensure_ascii=False) + ";\n"
        "const CASES = " + json.dumps(SCREENSHOT_CASES, ensure_ascii=False) + ";\n"
        "const PROTECTED = " + json.dumps(PROTECTED_VALUES, ensure_ascii=False) + ";\n"
        + javascript
    )
    script = tmp_path / "english-0504.cjs"
    script.write_text(program, encoding="utf-8")
    completed = subprocess.run([node, str(script)], check=True, capture_output=True, text=True)
    assert completed.stdout.startswith(f"PASS {len(SCREENSHOT_CASES)} cases")


def test_0504_source_files_and_storage_names_are_not_modified():
    # The translated strings affect presentation, never on-disk paths.
    assert UI_TRANSLATIONS["Papierkorb"] == "Trash"
    assert "data-bk-preserve-language" in EVENTS_HTML
    from app.storage_config import load_storage_settings
    assert callable(load_storage_settings)
